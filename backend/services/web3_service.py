import os
import uuid
from core.logger import logger

# ✅ PURE MOCK MODE (NO WEB3 DEPENDENCY)
# This ensures zero-claim payouts are visible in the UI without real blockchain overhead.

SEPOLIA_RPC = os.getenv("SEPOLIA_RPC", "https://ethereum-sepolia.publicnode.com")
PRIVATE_KEY = os.getenv("WEB3_PRIVATE_KEY", None)

async def send_payout_tx(recipient_address: str, inr_amount: float) -> dict:
    """
    Simulates sending ETH equivalent payout for demo purposes.
    Since we have removed the 'web3' library for lightweight deployment,
    this returns a 100% mocked transaction success state.
    """

    # 💰 Mock conversion (1 INR = ~0.0000035 ETH)
    eth_amount = round(inr_amount * 0.0000035, 6)

    # ✅ Validate address format (0x + 40 hex chars)
    if not recipient_address or len(recipient_address) != 42 or not recipient_address.startswith("0x"):
        logger.warning(f"Invalid Web3 address for display: {recipient_address}. Using mock address.")
        recipient_address = "0x" + os.urandom(20).hex()

    logger.info(f"[MOCK-PAYOUT] Simulating {eth_amount} ETH transfer to {recipient_address}")
    
    # Return a realistic-looking mock transaction response
    return {
        "status": "SUCCESS",
        "tx_hash": "0x" + uuid.uuid4().hex + uuid.uuid4().hex[:32],
        "amount": eth_amount,
        "recipient": recipient_address,
        "currency": "ETH",
        "mocked": True,
        "network": "Sepolia Simulation"
    }

def get_wallet_status():
    """Returns a simple status check for the dashboard."""
    return {
        "connected": True,
        "network": "SnapInsure Simulation Grid",
        "mode": "High-Fidelity Mock"
    }