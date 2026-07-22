import socket
import sys


def trigger_action(action: str = "TOGGLE"):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(action.encode('utf-8'), ("127.0.0.1", 15324))
        print(f"Command '{action}' sent successfully.")
    except Exception as e:
        print(f"Failed to send command: {e}")


if __name__ == "__main__":
    action = "TOGGLE"
    if len(sys.argv) > 1:
        action = sys.argv[1].upper()
    trigger_action(action)
