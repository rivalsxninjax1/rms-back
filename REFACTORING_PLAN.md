# Database Model Refactoring Plan

## Issues Identified

### 1. Duplicate Table Models
- `core.Table` and `reservations.Table` serve similar purposes
- `inventory.Table` exists for asset management
- Need to consolidate and establish clear relationships

### 2. Missing Foreign Key Constraints
- Some models lack proper CASCADE/PROTECT constraints
- Missing related_name consistency
- Weak referential integrity in some relationships

### 3. Index Optimization
- Missing composite indexes for common query patterns
- Some indexes could be more efficient
- Need partial indexes for filtered queries

### 4. Data Integrity Issues
- Missing unique constraints on business logic fields
- Insufficient validation at database level
- Some models allow inconsistent states

### 5. Performance Issues
- Missing indexes on frequently queried fields
- Some relationships could benefit from select_related optimization
- Large text fields without proper indexing

## Refactoring Strategy

### Phase 1: Table Model Consolidation
1. Keep `core.Table` as the master table registry
2. Update `reservations.Table` to reference `core.Table`
3. Keep `inventory.Table` separate for asset management
4. Add proper foreign key relationships

### Phase 2: Constraint Enhancement
1. Add missing unique constraints
2. Improve foreign key constraints with proper CASCADE/PROTECT
3. Add check constraints for business logic validation
4. Enhance field-level validation

### Phase 3: Index Optimization
1. Add composite indexes for common query patterns
2. Add partial indexes for filtered queries
3. Optimize existing indexes
4. Add covering indexes where beneficial

### Phase 4: Relationship Improvements
1. Standardize related_name conventions
2. Add missing reverse relationships
3. Optimize select_related and prefetch_related usage
4. Add proper model managers for common queries

## Implementation Order
1. Core models (Organization, Location, Table)
2. User and authentication models
3. Menu and inventory models
4. Orders and reservations models
5. Supporting models (payments, coupons, etc.)