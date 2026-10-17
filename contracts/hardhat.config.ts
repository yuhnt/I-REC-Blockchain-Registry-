import type { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.28",
    // OpenZeppelin 5.6 dùng lệnh mcopy, cần EVM từ bản Cancun.
    settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: "cancun" },
  },
  // Bật bằng REPORT_GAS=true; dùng cho E3 (gas mỗi thao tác).
  gasReporter: { enabled: process.env.REPORT_GAS === "true" },
};

export default config;
