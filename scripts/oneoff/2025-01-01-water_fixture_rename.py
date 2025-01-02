"""There are some duplicate water type fixtures and inconsistent naming.

To address this the convention will now be principal substance first folled by a descending list
of concentation and name of each addative. For example, 'Water 2% Citric Acid', 'Hydrogel 1% NaCl'.

This script will migrate the water type 'Citric Acid Water 2%' to 'Water 2% Citric Acid'.
NB: This should be run after applying latest fixtures!

https://github.com/cortex-lab/alyx/issues/886
"""
from actions.models import WaterType, WaterAdministration, WaterRestriction

to_change = [
    ('Citric Acid 2.5%', 'Water 2.5% Citric Acid'),
    ('Citric Acid Water 3%', 'Water 3% Citric Acid'),
    ('Citric Acid Water 2%', 'Water 2% Citric Acid')
]
for old_name, new_name in to_change:
    try:
        old_water_type = WaterType.objects.get(name=old_name)
    except WaterType.DoesNotExist:
        continue
    try:
        # Test whether the new water type already exists
        correct_water_type = WaterType.objects.get(name=new_name)
        # Find all water administrations and restrictions with old water type
        water_administrations = WaterAdministration.objects.filter(water_type=old_water_type)
        water_restrictions = WaterRestriction.objects.filter(water_type=old_water_type)
        # Update the water type to new name
        n_updated = water_administrations.update(water_type=correct_water_type)
        n_updated += water_restrictions.update(water_type=correct_water_type)
        # Remove old water type
        affected, affected_models = old_water_type.delete()
        assert affected == 1, 'only one water type should have been deleted'
        print(f'New water type "{new_name}" added to {n_updated} records; "{old_name}" deleted')
    except WaterType.DoesNotExist:
        # If the new water type does not exist, simply rename the old one
        old_water_type.name = new_name
        old_water_type.save()
        print(f'Water type "{old_name}" has been renamed to "{new_name}"')