# judgment/profile.py
# Shim: from root profile.py + list_profiles wrapper
from profile import PersonalProfile, load_profile as _load_profile
from pathlib import Path

def list_profiles():
    """列出所有可用档案"""
    profiles_dir = Path('E:/juhuo/profiles')
    if not profiles_dir.exists():
        return []
    profiles = []
    for f in profiles_dir.glob('*.json'):
        profiles.append({
            'name': f.stem,
            'path': str(f),
            'size': f.stat().st_size,
        })
    return profiles

# Alias: web/app.py does 'from judgment.profile import ..., load as load_profile'
# load_profile -> PersonalProfile.load classmethod
load_profile = _load_profile

# Alias: some code does 'from judgment.profile import load'
# load -> PersonalProfile.load classmethod
load = PersonalProfile.load

__all__ = ['PersonalProfile', 'load_profile', 'load', 'list_profiles']
