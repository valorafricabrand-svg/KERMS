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