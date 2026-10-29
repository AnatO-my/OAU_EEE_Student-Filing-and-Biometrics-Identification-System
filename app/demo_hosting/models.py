from django.db import models


class CacheEntry(models.Model):
    """Schema expected by Django's DatabaseCache; shared across function instances."""
    cache_key = models.CharField(max_length=255, primary_key=True)
    value = models.TextField()
    expires = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "eee_demo_cache"
        default_permissions = ()


class StorageBudget(models.Model):
    """One locked row serializes quota checks, including concurrent uploads."""
    used_bytes = models.PositiveBigIntegerField(default=0)

    class Meta:
        default_permissions = ()


class StoredFile(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    content = models.BinaryField()
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
