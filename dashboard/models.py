
from django.db import models

# Projects
class RecoveryProject(models.Model):
    #id = models.AutoField()
    project_id = models.IntegerField(primary_key=True)
    sector = models.CharField(max_length=50, blank=True, null=True)
    program = models.CharField(max_length=100, blank=True, null=True)
    project_title = models.TextField(blank=True, null=True)
    project_description = models.TextField(blank=True, null=True)
    funding_status = models.CharField(max_length=20, blank=True, null=True)
    gip = models.CharField(max_length=50, blank=True, null=True)
    central_tender_board_link = models.TextField(blank=True, null=True)
    funding_agency = models.CharField(max_length=100, blank=True, null=True)
    implementing_agency = models.CharField(max_length=100, blank=True, null=True)
    project_total_funding_us = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    project_total_funding_vt = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    project_expenditure = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    project_timeframe_days = models.IntegerField(blank=True, null=True)
    type_of_disaster_operation = models.CharField(max_length=100, blank=True, null=True)
    key_risks_to_implementation = models.TextField(blank=True, null=True)
    gip_attachment = models.FileField(upload_to="attachments/gip/",null=True,blank=True)

    class Meta:
        db_table = "recovery_projects"
        #ordering = ["id"]
        managed = False

# Locations
class ProjectLocations(models.Model):
    #id = models.AutoField()
    #project = models.ForeignKey('RecoveryProject', models.DO_NOTHING, blank=True, null=True)
    project = models.ForeignKey('RecoveryProject',to_field='project_id',db_column='project_id',on_delete=models.DO_NOTHING,blank=True, null=True)
    province = models.CharField(max_length=100, blank=True, null=True)
    island = models.CharField(max_length=100, blank=True, null=True)
    area_council = models.CharField(max_length=100, blank=True, null=True)
    project_site = models.CharField(max_length=100, blank=True, null=True)
    gps_longtitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)  # max_digits and decimal_places have been guessed, as this database handles decimal fields as float
    gps_latitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)  # max_digits and decimal_places have been guessed, as this database handles decimal fields as float

    class Meta:
        managed = False
        db_table = 'project_locations'

# Status Indicators
class ProjectStatusIndicators(models.Model):
    #project = models.ForeignKey('RecoveryProject', models.DO_NOTHING, blank=True, null=True)
    project = models.ForeignKey(RecoveryProject, to_field="project_id", db_column="project_id", on_delete=models.DO_NOTHING, blank=True,null=True,related_name="status_indicators",)
    status_indicator = models.DecimalField(max_digits=10, decimal_places=5, blank=True, null=True)  # max_digits and decimal_places have been guessed, as this database handles decimal fields as float
    description = models.CharField(max_length=150, blank=True, null=True)
    attachment = models.FileField(upload_to="attachments/project_status_indicators/", blank=True, null=True)
    
    class Meta:
        managed = False
        db_table = 'project_status_indicators'

# Area Councils
class AreaCouncils(models.Model): 
    province = models.CharField(max_length=100, blank=True, null=True)
    island = models.CharField(max_length=100, blank=True, null=True)
    area_council = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'area_councils'
