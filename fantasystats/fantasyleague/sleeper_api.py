"""
Utility functions for interacting with the Sleeper API
"""
import requests
from django.conf import settings
from django.core.cache import cache
from typing import Dict, List, Optional


SLEEPER_API_BASE = "https://api.sleeper.app/v1"
SLEEPER_PLAYERS_CACHE_KEY = "sleeper_players"
# Cache players data for 24 hours (86400 seconds) - players data changes infrequently
SLEEPER_PLAYERS_CACHE_TTL = getattr(settings, 'SLEEPER_PLAYERS_CACHE_TTL', 86400)


def safe_int(value, default=0):
    """Safely convert a value to int, returning default if conversion fails or value is None"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """Safely convert a value to float, returning default if conversion fails or value is None"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_league_info(league_id: str) -> Optional[Dict]:
    """
    Retrieve league metadata for the given Sleeper league identifier.
    
    Returns:
        dict: Parsed league JSON on success, or `None` if `league_id` is falsy or the request or JSON parsing fails.
    """
    if not league_id:
        return None
    
    try:
        response = requests.get(f"{SLEEPER_API_BASE}/league/{league_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching league info: {e}")
        return None


def get_league_users(league_id: str) -> List[Dict]:
    """
    Fetch all users in a Sleeper league.
    
    Returns:
        List[Dict]: List of user objects returned by the Sleeper API. Returns an empty list if `league_id` is falsy or if a request/parse error occurs.
    """
    if not league_id:
        return []
    
    try:
        response = requests.get(f"{SLEEPER_API_BASE}/league/{league_id}/users", timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching league users: {e}")
        return []


def get_league_rosters(league_id: str) -> List[Dict]:
    """
    Fetch all rosters for the given league from the Sleeper API.
    
    Returns:
        List[Dict]: A list of roster objects parsed from the API response. Returns an empty list if `league_id` is falsy or if the request or response parsing fails.
    """
    if not league_id:
        return []
    
    try:
        response = requests.get(f"{SLEEPER_API_BASE}/league/{league_id}/rosters", timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching league rosters: {e}")
        return []


def get_players() -> Dict:
    """
    Fetch all NFL players from Sleeper API.
    Uses Django cache to avoid repeated fetches of the large dataset (~5MB).
    Cache TTL is configurable via SLEEPER_PLAYERS_CACHE_TTL setting (default: 24 hours).
    """
    # Check cache first
    cached_players = cache.get(SLEEPER_PLAYERS_CACHE_KEY)
    if cached_players is not None:
        print(f"DEBUG: Returning cached players data ({len(cached_players)} players)")
        return cached_players
    
    # Cache miss - fetch from API
    print("DEBUG: Cache miss - fetching players data from Sleeper API...")
    try:
        response = requests.get(f"{SLEEPER_API_BASE}/players/nfl", timeout=60)
        response.raise_for_status()
        players_data = response.json()
        
        # Cache the successful response
        cache.set(SLEEPER_PLAYERS_CACHE_KEY, players_data, SLEEPER_PLAYERS_CACHE_TTL)
        print(f"DEBUG: Cached players data ({len(players_data)} players) for {SLEEPER_PLAYERS_CACHE_TTL} seconds")
        
        return players_data
    except requests.Timeout:
        print("Timeout fetching players data (this is a large dataset)")
        # Don't cache error responses
        return {}
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching players: {e}")
        import traceback
        traceback.print_exc()
        # Don't cache error responses
        return {}
    except Exception as e:
        print(f"Unexpected error fetching players: {e}")
        import traceback
        traceback.print_exc()
        # Don't cache error responses
        return {}


def get_team_avatar_url(avatar_id: str, thumbnail: bool = True) -> str:
    """
    Build the Sleeper CDN URL for a team's or user's avatar.
    
    Parameters:
        avatar_id (str): Sleeper avatar identifier.
        thumbnail (bool): If True, return the thumbnail URL; otherwise return the full-size URL.
    
    Returns:
        str: The avatar URL, or an empty string if `avatar_id` is empty.
    """
    if not avatar_id:
        return ""
    
    if thumbnail:
        return f"https://sleepercdn.com/avatars/thumbs/{avatar_id}"
    return f"https://sleepercdn.com/avatars/{avatar_id}"


def get_league_teams(league_id: str) -> List[Dict]:
    """Fetch and combine league users and rosters to get team information.
    
    Note: This function makes fresh API calls each time - no caching.
    """
    """
    Assemble team entries for a Sleeper league by combining league users and rosters.
    
    Each returned team dictionary contains metadata for a single roster, including:
    `user_id`, `username`, `display_name`, `team_name`, `avatar`, `avatar_url`,
    `roster_id`, `division` (if available), `wins`, `losses`, `ties`, `fpts`,
    `fpts_decimal`, and `total_points` (calculated as `fpts + fpts_decimal/100`).
    
    Returns:
        teams (List[Dict]): A list of team dictionaries described above; empty if
        `league_id` is falsy or data cannot be retrieved.
    """
    if not league_id:
        print(f"DEBUG: get_league_teams called with empty league_id")
        return []
    
    print(f"DEBUG: get_league_teams fetching data for league_id: {league_id}")
    
    # Fetch league info to check for divisions
    league_info = get_league_info(league_id)
    divisions = []
    if league_info and league_info.get('settings'):
        # Divisions can be stored as a list of division names
        divisions_raw = league_info.get('settings', {}).get('divisions', [])
        if divisions_raw:
            # If it's a list of strings, use it directly
            if isinstance(divisions_raw, list) and divisions_raw and isinstance(divisions_raw[0], str):
                divisions = divisions_raw
            # If it's a number, create default division names
            elif isinstance(divisions_raw, (int, float)):
                divisions = [f"Division {i+1}" for i in range(int(divisions_raw))]
    
    # Fetch users and rosters
    users = get_league_users(league_id)
    rosters = get_league_rosters(league_id)
    
    # Create a mapping of owner_id to roster
    roster_by_owner = {roster['owner_id']: roster for roster in rosters if roster.get('owner_id')}
    
    # Combine user and roster data
    teams = []
    for user in users:
        user_id = user.get('user_id')
        if not user_id:
            continue
        
        roster = roster_by_owner.get(user_id)
        if not roster:
            continue
        
        # Get team name from metadata or use display_name
        metadata = user.get('metadata', {}) or {}
        team_name = metadata.get('team_name') or user.get('display_name') or user.get('username', 'Unknown Team')
        
        # Get division if available
        division = None
        if divisions:
            # Check multiple possible locations for division number
            division_num = None
            
            # Try roster settings first (most common location)
            if roster.get('settings'):
                division_num = roster.get('settings', {}).get('division', None)
            
            # If not found in settings, try roster level
            if division_num is None:
                division_num = roster.get('division', None)
            
            if division_num is not None:
                try:
                    division_num = int(division_num)
                    # Try 1-indexed first
                    if 1 <= division_num <= len(divisions):
                        division = divisions[division_num - 1]
                    # If that fails, fall back to 0-indexed
                    elif 0 <= division_num < len(divisions):
                        division = divisions[division_num]
                    else:
                        print(f"DEBUG: division_num {division_num} out of range for {len(divisions)} divisions")
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Error converting division_num: {e}")
                    pass
            
            if division is None and divisions:
                print(f"DEBUG: Team {team_name} has no division assigned. Roster keys: {list(roster.keys())}, settings keys: {list(roster.get('settings', {}).keys())}")
        
        # Safely extract and convert numeric values from roster settings
        # Explicitly handle None values - .get() with defaults only protects against missing keys, not None
        settings = roster.get('settings', {}) or {}
        
        # Get raw values - these may be None even if keys exist
        fpts_raw = settings.get('fpts')
        fpts_decimal_raw = settings.get('fpts_decimal')
        
        # Explicitly convert to float, handling None and non-numeric types
        fpts = safe_float(fpts_raw, 0.0)
        fpts_decimal = safe_float(fpts_decimal_raw, 0.0)
        
        # Calculate total points with explicit type conversion
        total_points = fpts + (fpts_decimal / 100.0)
        
        team_data = {
            'user_id': user_id,
            'username': user.get('username', ''),
            'display_name': user.get('display_name', ''),
            'team_name': team_name,
            'avatar': user.get('avatar', ''),
            'avatar_url': get_team_avatar_url(user.get('avatar', '')),
            'roster_id': roster.get('roster_id'),
            'division': division,
            'wins': safe_int(settings.get('wins'), 0),
            'losses': safe_int(settings.get('losses'), 0),
            'ties': safe_int(settings.get('ties'), 0),
            'fpts': fpts,
            'fpts_decimal': fpts_decimal,
            'total_points': total_points,
        }
        teams.append(team_data)
    
    # Sort by division if available, then by team name
    if divisions:
        teams.sort(key=lambda x: (x['division'] or '', x['team_name']))
    else:
        teams.sort(key=lambda x: x['team_name'])
    
    print(f"DEBUG: get_league_teams returning {len(teams)} teams for league_id: {league_id}")
    return teams


def get_team_by_roster_id(league_id: str, roster_id: int) -> Optional[Dict]:
    """Get a specific team's information by roster_id"""
    if not league_id or roster_id is None:
        return None
    
    teams = get_league_teams(league_id)
    for team in teams:
        # Handle both int and string roster_id comparisons
        team_roster_id = team.get('roster_id')
        if team_roster_id == roster_id or str(team_roster_id) == str(roster_id):
            return team
    return None


def get_roster_players(league_id: str, roster_id: int) -> List[Dict]:
    """Get the current roster players for a specific roster"""
    if not league_id or roster_id is None:
        return []
    
    try:
        rosters = get_league_rosters(league_id)
        print(f"DEBUG: Looking for roster_id={roster_id}, found {len(rosters)} rosters")
        
        for roster in rosters:
            # Handle both int and string roster_id comparisons
            roster_id_from_api = roster.get('roster_id')
            if roster_id_from_api == roster_id or str(roster_id_from_api) == str(roster_id):
                player_ids = roster.get('players') or []
                starters = roster.get('starters') or []
                reserve = roster.get('reserve') or []
                
                print(f"DEBUG: Found roster with {len(player_ids)} players, {len(starters)} starters, {len(reserve)} reserve")
                print(f"DEBUG: player_ids empty? {not player_ids}, starters exists? {bool(starters)}")
                
                # If players list is empty but we have starters, use starters + reserve as the player list
                # Check explicitly for empty list and non-empty starters
                if len(player_ids) == 0 and len(starters) > 0:
                    print(f"DEBUG: players list is empty, using starters and reserve as player list")
                    # Combine starters and reserve, removing duplicates
                    all_player_ids = list(set(starters + reserve))
                    player_ids = all_player_ids
                    print(f"DEBUG: Combined player list has {len(player_ids)} players")
                elif not player_ids:
                    print(f"DEBUG: WARNING - No players and no starters found in roster!")
                
                # Convert all to strings for consistent comparison
                starters_set = {str(s) for s in starters}
                reserve_set = {str(r) for r in reserve}
                
                # Fetch player data (this is a large call, might be slow)
                players_data = {}
                try:
                    print("DEBUG: Fetching players data...")
                    players_data = get_players()
                    print(f"DEBUG: Fetched {len(players_data)} players")
                except Exception as e:
                    print(f"Error fetching players data: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue without player data - we'll show player IDs
                
                roster_players = []
                for player_id in player_ids:
                    player_id_str = str(player_id)
                    player_info = players_data.get(player_id_str, {}) if players_data else {}
                    
                    # If player info not found, still add player with minimal info
                    if not player_info:
                        roster_players.append({
                            'player_id': player_id,
                            'name': f"Player {player_id}",
                            'position': '',
                            'team': '',
                            'is_starter': player_id_str in starters_set,
                            'is_reserve': player_id_str in reserve_set,
                        })
                    else:
                        roster_players.append({
                            'player_id': player_id,
                            'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip() or f"Player {player_id}",
                            'position': player_info.get('position', ''),
                            'team': player_info.get('team', ''),
                            'is_starter': player_id_str in starters_set,
                            'is_reserve': player_id_str in reserve_set,
                        })
                
                print(f"DEBUG: Returning {len(roster_players)} roster players")
                return roster_players
        
        print(f"DEBUG: Roster with id {roster_id} not found")
        return []
    except Exception as e:
        print(f"Error in get_roster_players: {e}")
        import traceback
        traceback.print_exc()
        return []