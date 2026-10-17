import { expect } from "chai";
import { ethers } from "hardhat";

// Test tạm của giai đoạn 0: xác nhận Hardhat Network, solc và OpenZeppelin hoạt động.
describe("Toolchain", () => {
  it("chạy trên Hardhat Network cục bộ", async () => {
    const { chainId } = await ethers.provider.getNetwork();
    expect(chainId).to.equal(31337n);
  });

  it("deploy được contract ERC-1155 của OpenZeppelin và chuyển token theo Wh", async () => {
    const [plant, buyer] = await ethers.getSigners();
    const token = await ethers.deployContract("ToolchainCheck");

    await token.mint(plant.address, 1n, 500_000n);
    await token.connect(plant).safeTransferFrom(plant.address, buyer.address, 1n, 200_000n, "0x");

    expect(await token.balanceOf(plant.address, 1n)).to.equal(300_000n);
    expect(await token.balanceOf(buyer.address, 1n)).to.equal(200_000n);
  });
});
