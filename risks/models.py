from django.db import models


class RiskCategory(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=80, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "risk categories"

    def __str__(self):
        return f"{self.code} - {self.name}"


class RiskTheme(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class EnterpriseFunction(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StrategicObjective(models.Model):
    name = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExternalStakeholder(models.Model):
    name = models.CharField(max_length=120, unique=True)
    accountable_party = models.CharField(max_length=255, blank=True)
    influence_mechanism = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RiskAppetite(models.Model):
    name = models.CharField(max_length=20, unique=True)
    tolerance_threshold = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["tolerance_threshold", "name"]

    def __str__(self):
        return f"{self.name} ({self.tolerance_threshold})"