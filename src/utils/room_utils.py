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


def generate_room_password_from_number(room_number: str) -> str:
    """
    Generate entry password from room number (고정 매핑만 사용)

    Args:
        room_number: Room number (e.g., "101", "302")

    Returns:
        str: Entry password (매핑에 없으면 기본값 반환)
    """
    return ROOM_NUMBER_PASSWORDS.get(room_number, DEFAULT_ROOM_PASSWORD)


def is_valid_room_number(room_number: str) -> bool:
    """
    Check if room number has a password in mapping

    Args:
        room_number: Room number

    Returns:
        bool: True if room has password mapping

    """
    return room_number in ROOM_NUMBER_PASSWORDS
