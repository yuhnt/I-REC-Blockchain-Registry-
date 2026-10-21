import type { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

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
    },
  },
  // Bật bằng REPORT_GAS=true; dùng cho E3 (gas mỗi thao tác).
  gasReporter: { enabled: process.env.REPORT_GAS === "true" },
};

export default config;
