from django.db import models


class League(models.Model):
    id = models.IntegerField(primary_key=True)
    roster_positions = models.CharField(max_length=200)
    draft_id = models.IntegerField()
    scoring_settings = models.CharField(max_length=200)
    season = models.IntegerField()
    divisions = models.CharField(max_length=200)


class User(models.Model):
    user_name = models.CharField(max_length=200)
    user_id = models.IntegerField(primary_key=True)
    display_name = models.CharField(max_length=200)
    avatar = models.CharField(max_length=200)
    team_id = models.IntegerField()



class Teams(models.Model):
    team_name = models.CharField(max_length=200)
    team_id = models.IntegerField(primary_key=True)
    user_id = models.IntegerField()
    roster = models.CharField(max_length=200)
