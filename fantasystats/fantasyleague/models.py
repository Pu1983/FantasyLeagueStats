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


class NFLTeam(models.Model):
    """NFL Team information"""
    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    city = models.CharField(max_length=100)
    conference = models.CharField(max_length=3, choices=[('AFC', 'AFC'), ('NFC', 'NFC')], blank=True)
    division = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "NFL Team"
        verbose_name_plural = "NFL Teams"
    
    def __str__(self):
        return f"{self.city} {self.name}"


class NFLTeamStats(models.Model):
    """Fantasy statistics for NFL teams per season"""
    nfl_team = models.ForeignKey(NFLTeam, on_delete=models.CASCADE, related_name='stats')
    season = models.IntegerField()
    total_fantasy_points = models.FloatField(default=0.0)
    games_played = models.IntegerField(default=0)
    average_points = models.FloatField(default=0.0)
    total_touchdowns = models.IntegerField(default=0)
    total_yards = models.IntegerField(default=0)
    passing_yards = models.IntegerField(default=0)
    rushing_yards = models.IntegerField(default=0)
    receiving_yards = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-season', 'nfl_team']
        unique_together = ['nfl_team', 'season']
        verbose_name = "NFL Team Stat"
        verbose_name_plural = "NFL Team Stats"
    
    def __str__(self):
        return f"{self.nfl_team} - {self.season} Season"
    
    def save(self, *args, **kwargs):
        """Calculate average points when saving"""
        if self.games_played > 0:
            self.average_points = self.total_fantasy_points / self.games_played
        else:
            self.average_points = 0.0
        super().save(*args, **kwargs)


class Matchup(models.Model):
    """Individual fantasy league matchup/game"""
    season = models.IntegerField()
    week = models.IntegerField()
    team1 = models.ForeignKey(Teams, on_delete=models.CASCADE, related_name='matchups_as_team1')
    team2 = models.ForeignKey(Teams, on_delete=models.CASCADE, related_name='matchups_as_team2')
    team1_score = models.FloatField(default=0.0)
    team2_score = models.FloatField(default=0.0)
    match_date = models.DateField(null=True, blank=True)
    is_playoff = models.BooleanField(default=False)
    is_championship = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-season', '-week', 'match_date']
        verbose_name = "Matchup"
        verbose_name_plural = "Matchups"
    
    def __str__(self):
        return f"Week {self.week}, {self.season}: {self.team1.team_name} vs {self.team2.team_name}"
    
    def winner(self):
        """Return the winning team"""
        if self.team1_score > self.team2_score:
            return self.team1
        elif self.team2_score > self.team1_score:
            return self.team2
        return None  # Tie


class PlayerScore(models.Model):
    """Individual player performance in a matchup"""
    matchup = models.ForeignKey(Matchup, on_delete=models.CASCADE, related_name='player_scores')
    player_name = models.CharField(max_length=200)
    team = models.ForeignKey(Teams, on_delete=models.CASCADE, related_name='player_scores')
    position = models.CharField(max_length=10, blank=True)
    fantasy_points = models.FloatField(default=0.0)
    nfl_team = models.ForeignKey(NFLTeam, on_delete=models.SET_NULL, null=True, blank=True, related_name='player_scores')
    
    class Meta:
        ordering = ['-fantasy_points']
        verbose_name = "Player Score"
        verbose_name_plural = "Player Scores"
    
    def __str__(self):
        return f"{self.player_name} ({self.team.team_name}) - {self.fantasy_points} pts"


class TeamRanking(models.Model):
    """Season rankings for fantasy teams"""
    team = models.ForeignKey(Teams, on_delete=models.CASCADE, related_name='rankings')
    season = models.IntegerField()
    rank = models.IntegerField()
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    ties = models.IntegerField(default=0)
    total_points = models.FloatField(default=0.0)
    average_points = models.FloatField(default=0.0)
    playoff_appearance = models.BooleanField(default=False)
    championship = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-season', 'rank']
        unique_together = ['team', 'season']
        verbose_name = "Team Ranking"
        verbose_name_plural = "Team Rankings"
    
    def __str__(self):
        return f"{self.team.team_name} - {self.season} Season (Rank: {self.rank})"
    
    def save(self, *args, **kwargs):
        """Calculate average points when saving"""
        total_games = self.wins + self.losses + self.ties
        if total_games > 0:
            self.average_points = self.total_points / total_games
        else:
            self.average_points = 0.0
        super().save(*args, **kwargs)
