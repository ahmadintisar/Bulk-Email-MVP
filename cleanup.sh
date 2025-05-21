#!/bin/bash

# Cleanup script for custom templates
echo "Cleaning up custom templates directory..."

# Remove all HTML files from custom_templates directory
rm -f templates/custom_templates/*.html

# Remove subjects.json if it exists
rm -f templates/custom_templates/subjects.json

# Create empty directories if they don't exist
mkdir -p templates/custom_templates

echo "Cleanup completed successfully!" 