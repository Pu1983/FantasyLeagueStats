from django.contrib import admin
from .models import (
    League, User, Teams, NFLTeam, NFLTeamStats,
    Matchup, PlayerScore, TeamRanking
)


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ['id', 'season', 'draft_id']
    list_filter = ['season']
    search_fields = ['id']


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'user_name', 'display_name', 'team_id']
    search_fields = ['user_name', 'display_name']


@admin.register(Teams)
class TeamsAdmin(admin.ModelAdmin):
    list_display = ['team_id', 'team_name', 'user_id']
    search_fields = ['team_name']
    list_filter = ['user_id']


@admin.register(NFLTeam)
class NFLTeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'city', 'conference', 'division']
    list_filter = ['conference', 'division']
    search_fields = ['name', 'city', 'abbreviation']


@admin.register(NFLTeamStats)
class NFLTeamStatsAdmin(admin.ModelAdmin):
    list_display = ['nfl_team', 'season', 'total_fantasy_points', 'games_played', 'average_points']
    list_filter = ['season', 'nfl_team']
    search_fields = ['nfl_team__name']
    ordering = ['-season', 'nfl_team']


@admin.register(Matchup)
class MatchupAdmin(admin.ModelAdmin):
    list_display = ['season', 'week', 'team1', 'team2', 'team1_score', 'team2_score', 'match_date', 'is_playoff', 'is_championship']
    list_filter = ['season', 'week', 'is_playoff', 'is_championship']
    search_fields = ['team1__team_name', 'team2__team_name']
    ordering = ['-season', '-week']
    date_hierarchy = 'match_date'


@admin.register(PlayerScore)
class PlayerScoreAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'team', 'position', 'fantasy_points', 'nfl_team', 'matchup']
    list_filter = ['position', 'team', 'nfl_team']
    search_fields = ['player_name', 'team__team_name']
    ordering = ['-fantasy_points']
    raw_id_fields = ['matchup', 'team', 'nfl_team']


@admin.register(TeamRanking)
class TeamRankingAdmin(admin.ModelAdmin):
    list_display = ['team', 'season', 'rank', 'wins', 'losses', 'ties', 'total_points', 'average_points', 'playoff_appearance', 'championship']
    list_filter = ['season', 'playoff_appearance', 'championship']
    search_fields = ['team__team_name']
    ordering = ['-season', 'rank']
    list_editable = ['rank', 'wins', 'losses', 'ties']
