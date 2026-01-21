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
    # Use bulk queries with annotations to avoid N+1 queries
    teams = Teams.objects.annotate(
        total_wins=Sum('rankings__wins'),
        total_losses=Sum('rankings__losses'),
        championships=Count('rankings__id', filter=Q(rankings__championship=True)),
        seasons_played=Count('rankings__id', distinct=True),
        best_rank=Min('rankings__rank')
    ).order_by('team_name')
    
    # Build teams_with_stats list from annotated queryset
    teams_with_stats = []
    for team in teams:
        teams_with_stats.append({
            'team': team,
            'total_wins': team.total_wins or 0,
            'total_losses': team.total_losses or 0,
            'championships': team.championships or 0,
            'best_rank': team.best_rank or 0,
            'seasons_played': team.seasons_played or 0,
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
    best_rank = rankings.aggregate(Min('rank'))['rank__min'] or 0
    worst_rank = rankings.aggregate(Max('rank'))['rank__max'] or 0
    
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
