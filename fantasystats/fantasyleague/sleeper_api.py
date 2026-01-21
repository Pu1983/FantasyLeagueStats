"""
Utility functions for interacting with the Sleeper API
"""
import requests
from django.conf import settings
from typing import Dict, List, Optional


SLEEPER_API_BASE = "https://api.sleeper.app/v1"


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
    """Fetch league information from Sleeper API"""
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
    """Fetch all users in a league from Sleeper API"""
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
    """Fetch all rosters in a league from Sleeper API"""
    if not league_id:
        return []
    
    try:
        response = requests.get(f"{SLEEPER_API_BASE}/league/{league_id}/rosters", timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching league rosters: {e}")
        return []


def get_team_avatar_url(avatar_id: str, thumbnail: bool = True) -> str:
    """Get the avatar URL for a team/user"""
    if not avatar_id:
        return ""
    
    if thumbnail:
        return f"https://sleepercdn.com/avatars/thumbs/{avatar_id}"
    return f"https://sleepercdn.com/avatars/{avatar_id}"


def get_league_teams(league_id: str) -> List[Dict]:
    """
    Fetch and combine league users and rosters to get team information.
    Returns a list of team dictionaries with:
    - user_id
    - username
    - display_name
    - team_name (from metadata)
    - avatar
    - avatar_url
    - roster_id
    - division (if available)
    - wins, losses, ties, fpts (from roster settings)
    """
    if not league_id:
        return []
    
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
        if divisions and roster.get('settings'):
            # Some leagues store division number (0-indexed) in roster settings
            division_num = roster.get('settings', {}).get('division', None)
            if division_num is not None:
                try:
                    division_num = int(division_num)
                    if 0 <= division_num < len(divisions):
                        division = divisions[division_num]
                except (ValueError, TypeError):
                    pass
        
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
    
    return teams
