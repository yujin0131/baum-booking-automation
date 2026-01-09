"""
Room utility functions
객실 관련 유틸리티 함수
"""
from .constants import ROOM_NUMBER_PASSWORDS, DEFAULT_ROOM_PASSWORD


def get_room_password_for_room(room_number: str) -> str:
    """
    Get entry password for room number (fixed passwords)

    Args:
        room_number: Room number (e.g., "101", "302")

    Returns:
        str: Entry password for the room (or default if not found)
    """
    return ROOM_NUMBER_PASSWORDS.get(room_number, DEFAULT_ROOM_PASSWORD)
