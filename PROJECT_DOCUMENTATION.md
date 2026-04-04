# FundMe Technical Documentation

## 1. Project Overview
**FundMe** is a decentralized crowdfunding platform built on the **Ethereum Sepolia Testnet**. Unlike traditional platforms, FundMe introduces a **Milestone-Based Funding** model, where funds are held in escrow and released only after project milestones are completed and approved by a majority of donors. This ensures accountability, transparency, and donor protection.

---

## 2. Core Features
*   **Decentralized Escrow**: Funds are managed by an immutable smart contract, not a central authority.
*   **Milestone-Based Withdrawals**: Creators cannot withdraw all funds at once. They must define milestones (e.g., 20%, 30%, 50%).
*   **Donor Voting Power**: Donors have voting rights proportional to their contribution. A 50% majority (by weighted donation) is required for fund releases.
*   **Transparent Refund Policy**: If a campaign fails to reach its goal by the deadline, donors can claim their funds back directly.
*   **IPFS Integration**: Campaign metadata and images are stored on IPFS via Pinata for censorship-resistant hosting.

---

## 3. Smart Contract Architecture (`FundMe.sol`)

### 3.1. Data Structures
*   **`Campaign`**: Stores title, description, goal, deadline, amount raised, and status.
*   **`Milestone`**: Defines description, percentage, approval votes, and withdrawal status.
*   **`Donation`**: Records donor address and individual contribution amount.

### 3.2. Core Functionalities
| Function | Description | Access Control |
| :--- | :--- | :--- |
| `createCampaign` | Initializes a new campaign with milestones. | Anyone |
| `donate` | Contributes ETH to a specific campaign. | Anyone |
| `voteOnMilestone` | Casts a weighted vote for a milestone. | Donors Only |
| `withdrawMilestone` | Releases milestone funds if >50% approval. | Creator Only |
| `refund` | Claims back ETH if goal is not met by deadline. | Donors Only |

### 3.3. Security Implementation
*   **Reentrancy Protection**: Uses a custom `nonReentrant` modifier on all fund transfers.
*   **Gas Optimization**: Uses `error` codes and `revert` instead of long strings for lower gas consumption.
*   **Validation**: Ensures total milestone percentages equal exactly 100%.

---

## 4. Frontend Architecture (React)

### 4.1. Technology Stack
*   **React 19**: Modern UI framework for building the dashboard.
*   **Ethers.js v6**: Connects the browser to the Sepolia network.
*   **Tailwind CSS**: Used for the premium, responsive UI design.
*   **IPFS (Pinata)**: Decentralized storage for campaign assets.

### 4.2. Custom Hook (`useCampaigns.js`)
Handles the heavy lifting of:
- **Real-time Synchronization**: Listens to contract events (`Voted`, `DonationReceived`) to update the UI instantly.
- **Error Mapping**: Translates raw EVM error codes (e.g., `0xb0f74114`) into human-readable warnings.

---

## 5. Deployment & Configuration

### 5.1. Smart Contract (Hardhat)
1.  Configure `.env` with `SEPOLIA_RPC_URL` and `PRIVATE_KEY`.
2.  Compile: `npx hardhat compile`
3.  Deploy to Sepolia:
    ```powershell
    npx hardhat ignition deploy ignition/modules/FundMe.ts --network sepolia
    ```
4.  Copy the resulting address and update `frontend/src/contractAddress.js`.

### 5.2. Frontend Local Development
1.  `cd frontend`
2.  Install: `npm install`
3.  Run: `npm start` (Connect MetaMask to Sepolia network).

### 5.3. Production Deployment (Vercel)
The project is optimized for Vercel deployment:
1.  Navigate to `frontend`.
2.  Deploy via Vercel CLI:
    ```powershell
    vercel --prod
    ```
3.  Live URL: [fundme-dapp-rho.vercel.app](https://fundme-dapp-rho.vercel.app)

---

## 6. Usage Guide
### 6.1. For Creators
- Connect wallet -> Click "Create Campaign" -> Define Milestones -> Confirm on MetaMask.
- Once a milestone is "Ready", wait for donor approval to withdraw that portion of the funds.

### 6.2. For Donors
- Browse campaigns -> Donate (Min 0.001 ETH) -> Monitor progress.
- Navigate to the project's milestone tab to **Vote** on whether the creator has fulfilled their stage promise.

---

## 7. Future Roadmap
- **Governance Tokens**: Incentivizing active donors with voting power bonuses.
- **DAO Dispute Resolution**: Decentralized third-party mediation for contested milestones.
- **Mobile Integration**: Progressive Web App (PWA) for mobile-first donations.
