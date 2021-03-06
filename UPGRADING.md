# Upgrading
## 0.x.y -> 1.0.0

**WARNING: This is a DESTRUCTIVE operation. You will lose outstanding**
**requests as well as permissions to the blueprint app.**

### Step 1 - Preparation

#### Prepare Server
Shut down your supervisor (any running server / worker processes).

#### Change ESI Application Settings

Ensure that your ESI application requests the following roles:

:small_blue_diamond: = New
 - `esi-assets.read_assets.v1` :small_blue_diamond:
 - `esi-assets.read_corporation_assets.v1`
 - `esi-characters.read_blueprints.v1` :small_blue_diamond:
 - `esi-corporations.read_blueprints.v1`
 - `esi-industry.read_character_jobs.v1` :small_blue_diamond:
 - `esi-industry.read_corporation_jobs.v1` :small_blue_diamond:
 - `esi-universe.read_structures.v1`

### Step 2 - Reset Migrations

Reset migrations for blueprints:
```
./manage.py migrate blueprints zero --fake
```
### Step 3 - Clean the DB

Run the following SQL:
```sql
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS blueprints_blueprint;
DROP TABLE IF EXISTS blueprints_location;
DROP TABLE IF EXISTS blueprints_owner;
DROP TABLE IF EXISTS blueprints_request;
SET FOREIGN_KEY_CHECKS=1;
```

### Step 4 - Remove old permissions

Run the following in a django shell (`./manage.py shell`)
```python
from django.contrib.auth.models import Permission
Permission.objects.filter(content_type__app_label="blueprints").delete()
exit()
```

### Step 5 - Upgrade Package

```
pip install -U aa-blueprints
```

### Step 6 - Post-Install
```
./manage.py migrate
./manage.py collectstatic
```

### Step 7 - Completion
Bring your server back up, setup your blueprint related permissions (Under Blueprint ), and re-add your blueprint owners.
Then enjoy the new version of blueprints!
