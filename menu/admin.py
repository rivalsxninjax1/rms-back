from django.contrib import admin, messages
from django import forms
from django.urls import path
from django.template.response import TemplateResponse
from django.utils import timezone
from io import TextIOWrapper
import csv
from PIL import Image

from .models import MenuItem, MenuCategory, ModifierGroup, Modifier
from reports.models import AuditLog


# --- Forms -------------------------------------------------------------------

class MenuItemAdminForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make absolutely sure the FK has a full, valid queryset
        self.fields["category"].queryset = MenuCategory.objects.all()

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if not img:
            return img
        # Limit by size (<= 3MB)
        max_bytes = 3 * 1024 * 1024
        if getattr(img, 'size', 0) and img.size > max_bytes:
            raise forms.ValidationError("Image file too large (max 3MB).")
        # Validate actual image content
        try:
            img.file.seek(0)
            im = Image.open(img.file)
            im.verify()
        except Exception:
            raise forms.ValidationError("Invalid image file.")
        finally:
            try:
                img.file.seek(0)
            except Exception:
                pass
        # Optional dimension limit
        try:
            im2 = Image.open(img.file)
            w, h = im2.size
            if w > 3000 or h > 3000:
                raise forms.ValidationError("Image dimensions too large (max 3000x3000).")
        except Exception:
            pass
        finally:
            try:
                img.file.seek(0)
            except Exception:
                pass
        return img


# --- Admins ------------------------------------------------------------------

@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "sort_order", "available_now")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("sort_order", "name")

    def available_now(self, obj):
        try:
            return obj.is_available_now()
        except Exception:
            return True
    available_now.boolean = True

    # Audit
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Category {'updated' if change else 'created'}: {obj}", content_object=obj, changes=form.changed_data, request=request, category='menu')

    def delete_model(self, request, obj):
        AuditLog.log_action(request.user, 'DELETE', f"Category deleted: {obj}", content_object=obj, request=request, category='menu')
        super().delete_model(request, obj)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    form = MenuItemAdminForm

    # Use autocomplete instead of raw_id to prevent invalid values
    autocomplete_fields = ("category",)

    list_display = (
        "id",
        "name",
        "price",
        "is_available",
        "available_now",
        "category",
        "sort_order",
        "is_vegetarian",
        "created_at",
    )
    list_filter = ("is_available", "category", "is_vegetarian")
    search_fields = ("name", "description")
    list_select_related = ("category",)
    ordering = ("sort_order", "name")

    # Belt-and-suspenders: ensure admin widget uses a full queryset
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs.setdefault("queryset", MenuCategory.objects.all())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def available_now(self, obj):
        try:
            return obj.is_available_now()
        except Exception:
            return obj.is_available
    available_now.boolean = True

    # CSV Export/Import
    change_list_template = "admin/menu/menuitem/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="menu_menuitem_import_csv"),
            path("export-csv/", self.admin_site.admin_view(self.export_csv_view), name="menu_menuitem_export_csv"),
        ]
        return custom + urls

    def export_csv_view(self, request):
        # Export all (filtered) items
        qs = self.get_queryset(request)
        response = TemplateResponse(request, None)
        response['Content-Type'] = 'text/csv'
        response['Content-Disposition'] = 'attachment; filename="menu_items.csv"'
        rows = []
        header = [
            'id', 'name', 'category_id', 'price', 'is_available', 'available_from', 'available_until',
            'is_vegetarian', 'is_vegan', 'is_gluten_free', 'sort_order'
        ]
        def _row(mi: MenuItem):
            return [
                mi.id, mi.name, getattr(mi.category, 'id', ''), str(mi.price), mi.is_available,
                getattr(mi, 'available_from', '') or '', getattr(mi, 'available_until', '') or '',
                getattr(mi, 'is_vegetarian', False), getattr(mi, 'is_vegan', False), getattr(mi, 'is_gluten_free', False),
                getattr(mi, 'sort_order', 0),
            ]
        rows.append(header)
        for mi in qs:
            rows.append(_row(mi))
        # stream CSV
        import io
        sio = io.StringIO()
        writer = csv.writer(sio)
        writer.writerows(rows)
        response.content = sio.getvalue()
        # audit
        AuditLog.log_action(request.user, 'EXPORT', f"Exported {qs.count()} menu items to CSV", request=request, category='menu')
        return response

    def import_csv_view(self, request):
        ctx = dict(self.admin_site.each_context(request), title="Import Menu Items from CSV")
        if request.method == 'POST' and request.FILES.get('file'):
            f = request.FILES['file']
            try:
                wrapper = TextIOWrapper(f.file, encoding='utf-8')
                reader = csv.DictReader(wrapper)
                created = 0
                updated = 0
                for row in reader:
                    try:
                        cid = int(row.get('category_id') or 0)
                        category = MenuCategory.objects.get(pk=cid) if cid else None
                    except Exception:
                        category = None
                    defaults = {
                        'name': row.get('name') or '',
                        'category': category,
                        'price': row.get('price') or '0.00',
                        'is_available': (row.get('is_available') or 'True') in ('True','true','1'),
                        'available_from': row.get('available_from') or None,
                        'available_until': row.get('available_until') or None,
                    }
                    obj_id = row.get('id')
                    if obj_id:
                        try:
                            mi = MenuItem.objects.get(pk=int(obj_id))
                            for k, v in defaults.items():
                                setattr(mi, k, v)
                            mi.save()
                            updated += 1
                        except MenuItem.DoesNotExist:
                            mi = MenuItem.objects.create(**defaults)
                            created += 1
                    else:
                        MenuItem.objects.create(**defaults)
                        created += 1
                messages.success(request, f"Imported {created} created, {updated} updated")
                AuditLog.log_action(request.user, 'IMPORT', f"Imported items CSV (created={created}, updated={updated})", request=request, category='menu')
            except Exception as e:
                messages.error(request, f"Import failed: {e}")
        return TemplateResponse(request, 'admin/menu/import.html', ctx)

    # Audit
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Item {'updated' if change else 'created'}: {obj}", content_object=obj, changes=form.changed_data, request=request, category='menu')

    def delete_model(self, request, obj):
        AuditLog.log_action(request.user, 'DELETE', f"Item deleted: {obj}", content_object=obj, request=request, category='menu')
        super().delete_model(request, obj)


@admin.register(ModifierGroup)
class ModifierGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "menu_item", "is_required", "min_selections", "max_selections", "sort_order")
    list_filter = ("is_required", "menu_item__category")
    search_fields = ("name", "menu_item__name")
    autocomplete_fields = ("menu_item",)
    ordering = ("menu_item", "sort_order", "name")


@admin.register(Modifier)
class ModifierAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "modifier_group", "price", "is_available", "available_now", "sort_order")
    list_filter = ("is_available", "modifier_group__menu_item__category")
    search_fields = ("name", "modifier_group__name", "modifier_group__menu_item__name")
    autocomplete_fields = ("modifier_group",)
    ordering = ("modifier_group", "sort_order", "name")

    def available_now(self, obj):
        try:
            return obj.is_available_now()
        except Exception:
            return obj.is_available
    available_now.boolean = True

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Modifier {'updated' if change else 'created'}: {obj}", content_object=obj, changes=form.changed_data, request=request, category='menu')

    def delete_model(self, request, obj):
        AuditLog.log_action(request.user, 'DELETE', f"Modifier deleted: {obj}", content_object=obj, request=request, category='menu')
        super().delete_model(request, obj)
