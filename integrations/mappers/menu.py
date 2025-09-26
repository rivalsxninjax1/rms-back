from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ResolvedModifiers:
    resolved: List[Dict[str, Any]]
    conflicts: List[str]


class MenuMapper:
    """Transforms internal menu data into provider-specific payloads.

    This module defines the interface and reference implementation structure
    expected for production‑grade mapping of categories → items → variants →
    modifiers, including pricing matrices, availability rules, images, and
    localization. The concrete field mappings should be completed per provider
    spec.
    """

    def map_full_menu(self, internal_menu: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Transform internal menu to all platform formats.

        Return a dict keyed by platform identifier: { 'UBEREATS': {...}, 'DOORDASH': {...}, 'GRUBHUB': {...} }
        """
        ue_payload = self._map_for_ubereats(internal_menu)
        dd_payload = self._map_for_doordash(internal_menu)
        gh_payload = self._map_for_grubhub(internal_menu)
        return {"UBEREATS": ue_payload, "DOORDASH": dd_payload, "GRUBHUB": gh_payload}

    def handle_modifier_conflicts(self, modifiers: List[Dict[str, Any]]) -> ResolvedModifiers:
        """Resolve modifier conflicts across platforms.

        Example strategies:
        - Normalize duplicate modifier names with differing prices
        - Enforce platform-specific limits (e.g., max choices)
        - Split or merge groups where necessary
        """
        seen = {}
        conflicts: List[str] = []
        out: List[Dict[str, Any]] = []
        for m in modifiers:
            key = (m.get("name"), m.get("id"))
            if key in seen and seen[key].get("price") != m.get("price"):
                conflicts.append(f"Price conflict for {key}")
                # choose higher price by default
                if float(m.get("price", 0)) > float(seen[key].get("price", 0)):
                    seen[key] = m
            else:
                seen[key] = m
        out = list(seen.values())
        return ResolvedModifiers(resolved=out, conflicts=conflicts)

    def sync_availability_cascade(self, item_id: str, available: bool) -> None:
        """Cascade availability changes through the menu hierarchy.

        When an item becomes unavailable, mark its variants/modifiers unavailable.
        When available, re-enable according to business rules.
        """
        # Placeholder: Wire to internal MenuItem/Modifier models and propagate.
        return None

    # ---------------- Platform-specific private mappers -----------------

    def _map_for_ubereats(self, menu: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Translate internal structure to Uber Eats schema
        return {"categories": [], "items": []}

    def _map_for_doordash(self, menu: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Translate internal structure to DoorDash schema
        return {"categories": [], "items": []}

    def _map_for_grubhub(self, menu: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Translate internal structure to Grubhub schema
        return {"categories": [], "items": []}

