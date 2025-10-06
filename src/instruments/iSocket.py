"""iSocket module for RF instrument communication.

Provides socket-based communication with VSA and VSG instruments.
"""

import socket
import os
import logging


class iSocket:
    """Class for socket communication with RF instruments."""

    def __init__(self):
        """Initialize socket and logging."""
        # Setup logging to logs/iSocket.log
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'iSocket.log')
        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.idn = "Unknown"  # Placeholder for instrument ID

    def open(self, ip, port):
        """Connect to instrument at specified IP and port.

        Args:
            ip (str): Instrument IP address.
            port (int): Port number (e.g., 5025 for SCPI).

        Returns:
            iSocket: Self for method chaining.
        """
        try:
            self.sock.connect((ip, port))
            self.logger.info(f"Connected to {ip}:{port}")
            # Query instrument ID (example)
            self.idn = self.query('*IDN?').strip()
            return self
        except Exception as e:
            self.logger.error(f"Connection failed to {ip}:{port}: {e}")
            raise

    def close(self):
        """Close the socket connection."""
        try:
            self.sock.close()
            self.logger.info("Socket closed")
        except Exception as e:
            self.logger.error(f"Failed to close socket: {e}")
            raise

    def query(self, cmd):
        """Send SCPI command and return response.

        Args:
            cmd (str): SCPI command to send.

        Returns:
            str: Instrument response.
        """
        try:
            self.logger.info(f"Query: {cmd}")
            self.sock.send(f"{cmd}\n".encode())
            response = self.sock.recv(1024).decode().strip()
            self.logger.info(f"Response: {response}")
            return response
        except Exception as e:
            self.logger.error(f"Query failed: {cmd}, Error: {e}")
            raise

    def write(self, cmd):
        """Send SCPI command without expecting a response.

        Args:
            cmd (str): SCPI command to send.
        """
        try:
            self.logger.info(f"Write: {cmd}")
            self.sock.send(f"{cmd}\n".encode())
        except Exception as e:
            self.logger.error(f"Write failed: {cmd}, Error: {e}")
            raise

    def queryFloat(self, cmd):
        """Send SCPI command and return response as float.

        Args:
            cmd (str): SCPI command to send.

        Returns:
            float: Parsed response.
        """
        return float(self.query(cmd))

    def clear_error(self):
        """Clear instrument error queue."""
        self.logger.info("Clearing error queue")
        self.query(':SYST:ERR?')

    def __del__(self):
        """Close socket."""
        if self.sock:
            self.sock.close()
            self.logger.info("Socket closed")


if __name__ == '__main__':
    # Example usage
    sock = iSocket()
    sock.open('192.168.200.10', 5025)
    print(sock.idn)