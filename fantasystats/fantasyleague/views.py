from django.shortcuts import render, get_object_or_404
from django.db.models import Max, Min, Sum, Q, Count, Avg
from .models import Teams, TeamRanking, Matchup, PlayerScore


def index(request):
    """Main dashboard showing overview stats"""
    total_teams = Teams.objects.count()
    total_seasons = TeamRanking.objects.values('season').distinct().count()
    
    # Get latest season
    latest_season = TeamRanking.objects.aggregate(Max('season'))['season__max']
    
    # Get top teams by total points across all seasons
    top_teams = Teams.objects.annotate(
        total_points=Sum('rankings__total_points')
    ).order_by('-total_points')[:5] if latest_season else []
    
    # Get recent champions
    recent_champions = TeamRanking.objects.filter(
        championship=True
    ).select_related('team').order_by('-season')[:5]
    
    context = {
        'total_teams': total_teams,
        'total_seasons': total_seasons,
        'latest_season': latest_season,
        'top_teams': top_teams,
        'recent_champions': recent_champions,
    }
    return render(request, 'fantasyleague/index.html', context)


def team_list(request):
    """Display all available fantasy league teams for selection"""
    teams = Teams.objects.all().order_by('team_name')
    
    # Get summary stats for each team
    teams_with_stats = []
    for team in teams:
        rankings = TeamRanking.objects.filter(team=team).order_by('-season')
        total_wins = sum(r.wins for r in rankings)
        total_losses = sum(r.losses for r in rankings)
        championships = rankings.filter(championship=True).count()
        best_rank = rankings.aggregate(Max('rank'))['rank__max'] or 0
        
        teams_with_stats.append({
            'team': team,
            'total_wins': total_wins,
            'total_losses': total_losses,
            'championships': championships,
            'best_rank': best_rank,
            'seasons_played': rankings.count(),
        })
    
    context = {
        'teams_with_stats': teams_with_stats,
    }
    return render(request, 'fantasyleague/team_list.html', context)


def team_detail(request, team_id):
    """Individual fantasy team detail page"""
    team = get_object_or_404(Teams, pk=team_id)
    
    # Get all rankings for this team
    rankings = TeamRanking.objects.filter(team=team).order_by('-season')
    
    # Calculate achievements
    championships = rankings.filter(championship=True).count()
    playoff_appearances = rankings.filter(playoff_appearance=True).count()
    total_wins = sum(r.wins for r in rankings)
    total_losses = sum(r.losses for r in rankings)
    total_ties = sum(r.ties for r in rankings)
    best_rank = rankings.aggregate(Max('rank'))['rank__max'] or 0
    worst_rank = rankings.aggregate(Min('rank'))['rank__min'] or 0
    
    # Get highest match score
    team1_matchups = Matchup.objects.filter(team1=team)
    team2_matchups = Matchup.objects.filter(team2=team)
    
    highest_match_score = None
    highest_match = None
    
    for matchup in team1_matchups:
        if matchup.team1_score > (highest_match_score or 0):
            highest_match_score = matchup.team1_score
            highest_match = matchup
    
    for matchup in team2_matchups:
        if matchup.team2_score > (highest_match_score or 0):
            highest_match_score = matchup.team2_score
            highest_match = matchup
    
    # Get highest individual player score
    highest_player_score = PlayerScore.objects.filter(
        team=team
    ).order_by('-fantasy_points').first()
    
    # Get all matchups for this team
    all_matchups = (team1_matchups | team2_matchups).order_by('-season', '-week')[:10]
    
    context = {
        'team': team,
        'rankings': rankings,
        'championships': championships,
        'playoff_appearances': playoff_appearances,
        'total_wins': total_wins,
        'total_losses': total_losses,
        'total_ties': total_ties,
        'best_rank': best_rank,
        'worst_rank': worst_rank,
        'highest_match': highest_match,
        'highest_match_score': highest_match_score,
        'highest_player_score': highest_player_score,
        'recent_matchups': all_matchups,
    }
    return render(request, 'fantasyleague/team_detail.html', context)


def team_insights(request, team_id):
    """Team insights page for historic data analysis"""
    team = get_object_or_404(Teams, pk=team_id)
    
    # Get all rankings
    rankings = TeamRanking.objects.filter(team=team).order_by('season')
    
    # Get all matchups
    team1_matchups = Matchup.objects.filter(team1=team)
    team2_matchups = Matchup.objects.filter(team2=team)
    all_matchups = (team1_matchups | team2_matchups).order_by('season', 'week')
    
    # Calculate season-by-season performance
    season_performance = []
    for ranking in rankings:
        season_matchups = all_matchups.filter(season=ranking.season)
        season_wins = sum(1 for m in season_matchups if (m.team1 == team and m.team1_score > m.team2_score) or (m.team2 == team and m.team2_score > m.team1_score))
        season_losses = sum(1 for m in season_matchups if (m.team1 == team and m.team1_score < m.team2_score) or (m.team2 == team and m.team2_score < m.team1_score))
        
        season_performance.append({
            'season': ranking.season,
            'rank': ranking.rank,
            'wins': ranking.wins,
            'losses': ranking.losses,
            'total_points': ranking.total_points,
            'average_points': ranking.average_points,
            'playoff': ranking.playoff_appearance,
            'championship': ranking.championship,
        })
    
    # Get top players for this team
    top_players = PlayerScore.objects.filter(team=team).values(
        'player_name'
    ).annotate(
        total_points=Sum('fantasy_points'),
        games=Count('id'),
        avg_points=Avg('fantasy_points')
    ).order_by('-total_points')[:10]
    
    context = {
        'team': team,
        'season_performance': season_performance,
        'top_players': top_players,
    }
    return render(request, 'fantasyleague/team_insights.html', context)
