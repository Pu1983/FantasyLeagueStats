from django.shortcuts import render, get_object_or_404
from django.db.models import Max, Min, Sum, Q, Count, Avg
from django.conf import settings
from .models import Teams, TeamRanking, Matchup, PlayerScore
from .sleeper_api import get_league_teams, get_team_by_roster_id, get_roster_players


def index(request):
    """
    Render the main dashboard with aggregated league overview statistics.
    
    Builds context containing total teams, total seasons, latest season, top teams by cumulative points, and recent champions, then renders the 'fantasyleague/index.html' template.
    
    Returns:
        HttpResponse: Rendered dashboard page with the computed context.
    """
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
    """
    Builds and renders the team selection page by merging current Sleeper league data with historical database statistics and grouping teams by division.
    
    Fetches league teams from the configured Sleeper league (if present), augments each team with aggregated historical stats from the local database (wins, losses, championships, best rank, seasons played), and groups the combined team records by division when divisions are present. Safe fallbacks are used when league configuration, Sleeper fields, or database records are missing; team entries include a `has_db_record` flag and a `team_id` suitable for linking to the team detail page.
    
    Returns:
        HttpResponse: Rendered 'fantasyleague/team_list.html' response with context keys:
            - teams_with_stats: list of combined team dictionaries with current and historical stats
            - teams_by_division: mapping of division name to list of teams (or {'All Teams': [...]})
            - has_divisions: boolean indicating whether divisions were detected
    """
    league_id = settings.SLEEPER_LEAGUE_ID
    print(f"DEBUG: team_list using league_id: {league_id}")
    
    # Fetch teams from Sleeper API
    sleeper_teams = get_league_teams(league_id) if league_id else []
    print(f"DEBUG: Fetched {len(sleeper_teams)} teams from Sleeper API")
    
    # Also get database stats if available
    db_teams = Teams.objects.annotate(
        total_wins=Sum('rankings__wins'),
        total_losses=Sum('rankings__losses'),
        championships=Count('rankings__id', filter=Q(rankings__championship=True)),
        seasons_played=Count('rankings__id', distinct=True),
        best_rank=Min('rankings__rank')
    )
    
    # Create a mapping of user_id to database stats
    db_stats_by_user = {}
    for team in db_teams:
        db_stats_by_user[team.user_id] = {
            'total_wins': team.total_wins or 0,
            'total_losses': team.total_losses or 0,
            'championships': team.championships or 0,
            'best_rank': team.best_rank or 0,
            'seasons_played': team.seasons_played or 0,
        }
    
    # Create a mapping of user_id to Teams model for linking
    db_teams_by_user = {team.user_id: team for team in Teams.objects.all()}
    
    # Combine Sleeper API data with database stats
    teams_with_stats = []
    divisions = set()
    
    for sleeper_team in sleeper_teams:
        user_id = sleeper_team.get('user_id')
        # Try to convert user_id to int for matching, handle both formats
        user_id_int = None
        if user_id:
            try:
                user_id_int = int(user_id)
            except (ValueError, TypeError):
                pass
        
        db_stats = db_stats_by_user.get(user_id_int, {}) if user_id_int else {}
        db_team = db_teams_by_user.get(user_id_int) if user_id_int else None
        
        division = sleeper_team.get('division')
        if division:
            divisions.add(division)
        
        # Use database team_id if available, otherwise use roster_id
        team_id = db_team.team_id if db_team else sleeper_team.get('roster_id')
        
        teams_with_stats.append({
            'team_name': sleeper_team.get('team_name', 'Unknown Team'),
            'display_name': sleeper_team.get('display_name', ''),
            'username': sleeper_team.get('username', ''),
            'avatar_url': sleeper_team.get('avatar_url', ''),
            'roster_id': sleeper_team.get('roster_id'),
            'user_id': user_id,
            'team_id': team_id,  # For linking to team_detail
            'division': division,
            'current_wins': sleeper_team.get('wins', 0),
            'current_losses': sleeper_team.get('losses', 0),
            'current_ties': sleeper_team.get('ties', 0),
            'current_points': sleeper_team.get('total_points', 0),
            # Historical stats from database
            'total_wins': db_stats.get('total_wins', 0),
            'total_losses': db_stats.get('total_losses', 0),
            'championships': db_stats.get('championships', 0),
            'best_rank': db_stats.get('best_rank', 0),
            'seasons_played': db_stats.get('seasons_played', 0),
            'has_db_record': db_team is not None,
        })
    
    # Group by division if divisions exist
    teams_by_division = {}
    if divisions:
        for team in teams_with_stats:
            div = team.get('division')
            # Only group teams that have a division assigned
            if div:
                if div not in teams_by_division:
                    teams_by_division[div] = []
                teams_by_division[div].append(team)
            else:
                teams_by_division.setdefault("Unassigned", []).append(team)
                # Log teams without division for debugging
                print(f"DEBUG: Team {team.get('team_name')} has no division assigned")
        
        # Sort divisions alphabetically
        sorted_divisions = sorted(teams_by_division.items(), key=lambda x: x[0])
        teams_by_division = dict(sorted_divisions)
    else:
        teams_by_division = {'All Teams': teams_with_stats}
    
    context = {
        'teams_with_stats': teams_with_stats,
        'teams_by_division': teams_by_division,
        'has_divisions': len(divisions) > 0,
    }
    return render(request, 'fantasyleague/team_list.html', context)


def team_detail(request, team_id):
    """Individual fantasy team detail page"""
    league_id = settings.SLEEPER_LEAGUE_ID
    
    # Try to get team from Sleeper API first (by roster_id)
    sleeper_team = None
    roster_players = []
    
    if league_id:
        try:
            roster_id = int(team_id)
            print(f"DEBUG: team_detail called with team_id={team_id}, converted to roster_id={roster_id}")
            sleeper_team = get_team_by_roster_id(league_id, roster_id)
            print(f"DEBUG: sleeper_team found: {sleeper_team is not None}")
            if sleeper_team:
                try:
                    print(f"DEBUG: Fetching roster players for roster_id={roster_id}")
                    roster_players = get_roster_players(league_id, roster_id)
                    print(f"DEBUG: Got {len(roster_players)} roster players")
                except Exception as e:
                    print(f"Error fetching roster players: {e}")
                    import traceback
                    traceback.print_exc()
                    roster_players = []  # Continue with empty roster
        except (ValueError, TypeError) as e:
            print(f"Error converting team_id to roster_id: {e}")
            pass
        except Exception as e:
            print(f"Unexpected error in team_detail (Sleeper): {e}")
            import traceback
            traceback.print_exc()
    
    # If not found in Sleeper, try database
    db_team = None
    rankings = []
    if not sleeper_team:
        try:
            db_team = Teams.objects.get(pk=team_id)
            # Get all rankings for this team
            rankings = TeamRanking.objects.filter(team=db_team).order_by('-season')
        except Teams.DoesNotExist:
            pass
    
    # If we have Sleeper team data, use it
    if sleeper_team:
        # Separate players by status
        starters = [p for p in roster_players if p.get('is_starter')]
        bench = [p for p in roster_players if not p.get('is_starter') and not p.get('is_reserve')]
        reserve = [p for p in roster_players if p.get('is_reserve')]
        
        context = {
            'team_name': sleeper_team.get('team_name', 'Unknown Team'),
            'avatar_url': sleeper_team.get('avatar_url', ''),
            'division': sleeper_team.get('division'),
            'starters': starters,
            'bench': bench,
            'reserve': reserve,
            'current_wins': sleeper_team.get('wins', 0),
            'current_losses': sleeper_team.get('losses', 0),
            'current_ties': sleeper_team.get('ties', 0),
            'current_points': sleeper_team.get('total_points', 0),
            'from_sleeper': True,
        }
        return render(request, 'fantasyleague/team_detail.html', context)
    
    # Fallback to database team if available
    if db_team:
        # Calculate achievements
        championships = rankings.filter(championship=True).count()
        playoff_appearances = rankings.filter(playoff_appearance=True).count()
        total_wins = sum(r.wins for r in rankings)
        total_losses = sum(r.losses for r in rankings)
        total_ties = sum(r.ties for r in rankings)
        best_rank = rankings.aggregate(Min('rank'))['rank__min'] or 0
        worst_rank = rankings.aggregate(Max('rank'))['rank__max'] or 0
        
        # Get highest match score
        team1_matchups = Matchup.objects.filter(team1=db_team)
        team2_matchups = Matchup.objects.filter(team2=db_team)
        
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
            team=db_team
        ).order_by('-fantasy_points').first()
        
        # Get all matchups for this team
        all_matchups = (team1_matchups | team2_matchups).order_by('-season', '-week')[:10]
        
        context = {
            'team': db_team,
            'team_name': db_team.team_name,
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
            'from_sleeper': False,
        }
        return render(request, 'fantasyleague/team_detail.html', context)
    
    # Team not found
    from django.http import Http404
    raise Http404("Team not found")


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