import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { CP, DAY, DEVICE_CAP_W, DEVICES, Reason, deploy, id, registerAll, reqId, submit } from "./fixture";

// Đăng ký, chuyển đăng ký, Production Group và kỳ phát hành (FLOW.md mục 8; I-REC §7.7, §8.2, §16.3).
describe("DeviceRegistry và kỳ phát hành", () => {
  async function ready() {
    const ctx = await deploy();
    await registerAll(ctx);
    return ctx;
  }

  it("IREC-7.7 L4: Production Group ≤ 5 MW và ≤ 50 cơ sở đăng ký được, vẫn chịu ngân sách CP", async () => {
    const ctx = await deploy();
    const g = id("G1");
    await expect(ctx.devices.connect(ctx.issuerA).registerDevice(g, CP, 720_000n, DAY - 30, true, 6))
      .to.emit(ctx.devices, "DeviceRegistered");
    await submit(ctx, DAY, 600_000n);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("g1"), g, DAY, [600_000n])).to.emit(ctx.gate, "Issued");
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("g2"), g, DAY, [1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("g2"), g, DAY, Reason.KEY);
  });

  it("IREC-7.7: nhóm quá 50 cơ sở bị revert InvalidGroup", async () => {
    const ctx = await deploy();
    await expect(ctx.devices.connect(ctx.issuerA).registerDevice(id("G2"), CP, 720_000n, DAY, true, 51))
      .to.be.revertedWithCustomError(ctx.devices, "InvalidGroup");
  });

  it("IREC-7.6: thiết bị phải gắn một CP đã biết và không vượt công suất CP", async () => {
    const ctx = await deploy();
    await expect(ctx.devices.connect(ctx.issuerA).registerDevice(id("B9"), id("CP-9"), DEVICE_CAP_W, DAY, false, 1))
      .to.be.revertedWithCustomError(ctx.devices, "UnknownCP");
    await expect(ctx.devices.connect(ctx.issuerA).registerDevice(id("B9"), CP, 720_001n, DAY, false, 1))
      .to.be.revertedWithCustomError(ctx.devices, "InvalidCapacity");
    await expect(ctx.devices.connect(ctx.outsider).registerDevice(id("B9"), CP, DEVICE_CAP_W, DAY, false, 1))
      .to.be.revertedWithCustomError(ctx.devices, "NotIssuer");
  });

  it("IREC-16.3 L3: chuyển đăng ký giữ nguyên mã; từ ngày hiệu lực chỉ issuer mới gửi được yêu cầu", async () => {
    const ctx = await loadFixture(ready);
    const b6 = DEVICES[5];
    await expect(ctx.devices.connect(ctx.issuerA).transferRegistration(b6, ctx.issuerB.address, DAY + 1))
      .to.emit(ctx.devices, "RegistrationTransferred").withArgs(b6, ctx.issuerA.address, ctx.issuerB.address, DAY + 1);
    await submit(ctx, DAY, 600_000n);
    await submit(ctx, DAY + 1, 600_000n);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a0"), b6, DAY, [100_000n])).to.emit(ctx.gate, "Issued");
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a1"), b6, DAY + 1, [100_000n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("a1"), b6, DAY + 1, Reason.NOT_ISSUER);
    await expect(ctx.gate.connect(ctx.issuerB).issue(reqId("b1"), b6, DAY + 1, [100_000n])).to.emit(ctx.gate, "Issued");
    const [, issuer] = await ctx.devices.deviceOf(b6);
    expect(issuer).to.equal(ctx.issuerB.address);
    await expect(ctx.devices.connect(ctx.issuerA).transferRegistration(b6, ctx.issuerA.address, DAY + 5))
      .to.be.revertedWithCustomError(ctx.devices, "NotCurrentIssuer");
  });

  it("IREC-8.2: kỳ vắt qua hai năm dương lịch → REJECT PERIOD", async () => {
    const ctx = await loadFixture(ready);
    const dec29 = 18990; // 29/12/2021
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("p"), DEVICES[0], dec29, Array(7).fill(1n)))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("p"), DEVICES[0], dec29, Reason.PERIOD);
  });

  it("IREC-8.2: kỳ bắt đầu trước ngày đăng ký hiệu lực → REJECT PERIOD", async () => {
    const ctx = await loadFixture(ready);
    const early = DAY - 31;
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("p"), DEVICES[0], early, [1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("p"), DEVICES[0], early, Reason.PERIOD);
  });

  it("IREC-8.2: kỳ từ ngày đóng đăng ký trở đi → REJECT PERIOD; ngày trước đó vẫn phát hành được", async () => {
    const ctx = await loadFixture(ready);
    await expect(ctx.devices.connect(ctx.issuerA).closeRegistration(DEVICES[0], DAY + 1))
      .to.emit(ctx.devices, "RegistrationClosed").withArgs(DEVICES[0], DAY + 1);
    await submit(ctx, DAY, 600_000n);
    await submit(ctx, DAY + 1, 600_000n);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [1n])).to.emit(ctx.gate, "Issued");
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("b"), DEVICES[0], DAY + 1, [1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("b"), DEVICES[0], DAY + 1, Reason.PERIOD);
  });

  it("IREC-8.2 / IREC-8.5: kỳ chưa kết thúc tại thời điểm nộp → REJECT PERIOD", async () => {
    const ctx = await loadFixture(ready);
    const today = Math.floor((await time.latest()) / 86400);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("f"), DEVICES[0], today, [1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("f"), DEVICES[0], today, Reason.PERIOD);
  });

  it("yearOf khớp lịch dương", async () => {
    const ctx = await loadFixture(ready);
    for (const iso of ["1970-01-01", "2020-02-29", "2021-12-31", "2022-01-01", "2023-11-30", "2100-03-01"]) {
      const day = Date.parse(iso) / 86400000;
      expect(await ctx.gate.yearOf(day)).to.equal(BigInt(iso.slice(0, 4)));
    }
    expect(ethers.isAddress(await ctx.gate.getAddress())).to.equal(true);
  });
});
