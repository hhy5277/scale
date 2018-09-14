"""Defines the application configuration for the scale import/export application"""

from django.apps import AppConfig


class PortConfig(AppConfig):
    """Configuration for the import/export app"""
    name = 'port'
    label = 'port'
    verbose_name = 'Import/Export'
