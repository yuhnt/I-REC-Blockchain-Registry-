import type { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";
import { existsSync, readFileSync } from "fs";
import { join } from "path";

// Đọc contracts/.env (không commit) mà không cần thêm thư viện: mỗi dòng KEY=VALUE, bỏ dấu ngoặc kép bao ngoài.
// Biến đã có trong môi trường được ưu tiên.
const envFile = join(__dirname, ".env");
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}
const { SEPOLIA_RPC_URL, TESTNET_MNEMONIC, ETHERSCAN_API_KEY } = process.env;

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.28",
    // OpenZeppelin 5.6 dùng lệnh mcopy, cần EVM từ bản Cancun. viaIR tránh lỗi "stack too deep" ở DecisionGate.
    settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "cancun", viaIR: true },
  },
  networks: {
    hardhat: {
      // Dòng sự kiện của E1 bắt đầu từ 2022; chain phải khởi đầu trước đó để đặt được timestamp theo đồng hồ mô phỏng.
      initialDate: process.env.REC_INITIAL_DATE,
      allowBlocksWithSameTimestamp: true,
      // Phí cơ sở bằng 0 để runner gửi giao dịch với gasPrice cố định, không phải hỏi phí ở mỗi giao dịch.
      initialBaseFeePerGas: 0,
      loggingEnabled: false,
      // E3: đào block mỗi REC_INTERVAL_MS mili giây (2 giây) để đo độ trễ; mặc định automine.
      mining: process.env.REC_INTERVAL_MS
        ? { auto: false, interval: Number(process.env.REC_INTERVAL_MS) }
        : { auto: true },
    },
    // Testnet công khai, chỉ để trình diễn tra cứu; thí nghiệm vẫn chạy trên Hardhat cục bộ.
    // 15 tài khoản suy ra từ TESTNET_MNEMONIC theo đúng thứ tự vai của rec/registry/chain_registry.py.
    ...(SEPOLIA_RPC_URL
      ? { sepolia: { url: SEPOLIA_RPC_URL, accounts: TESTNET_MNEMONIC ? { mnemonic: TESTNET_MNEMONIC, count: 15 } : [] } }
      : {}),
  },
  // Verify mã nguồn trên Sepolia Etherscan (Etherscan API V2: một key cho mọi mạng).
  etherscan: { apiKey: ETHERSCAN_API_KEY ?? "" },
  sourcify: { enabled: false },
  // Bật bằng REPORT_GAS=true; dùng cho E3 (gas mỗi thao tác).
  gasReporter: { enabled: process.env.REPORT_GAS === "true" },
};

export default config;
