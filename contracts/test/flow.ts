import { expect } from "chai";
import { loadFixture } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { CP, DAY, DEVICE_CAP_W, DEVICES, Reason, SUN_SLOTS, deploy, evidence, id, registerAll, reportsFor, reqId, submit,
  tokenId } from "./fixture";

// Luồng chính một lô (FLOW.md mục 4) và các kịch bản double counting D1–D5 ở chế độ R1 (SPEC mục 4.1).
describe("DecisionGate – luồng chính và lớp A", () => {
  async function ready() {
    const ctx = await deploy();
    await registerAll(ctx);
    return ctx;
  }

  it("IREC-7.1 / IREC-7.6 L1: lô sạch, 6 khối hợp lệ sau cùng CP đều được MINT, tổng bằng O1", async () => {
    const ctx = await loadFixture(ready);
    await submit(ctx, DAY, 600_000n);
    for (let i = 0; i < 6; i++) {
      await expect(ctx.gate.connect(ctx.issuerA).issue(reqId(`h${i}`), DEVICES[i], DAY, [100_000n]))
        .to.emit(ctx.gate, "Issued").withArgs(reqId(`h${i}`), tokenId(DEVICES[i], DAY), DEVICES[i], DAY, 100_000n,
          ctx.plant.address);
    }
    expect(await ctx.certs.issuedWh(CP, DAY)).to.equal(600_000n);
    expect(await ctx.certs.balanceOf(ctx.plant.address, tokenId(DEVICES[0], DAY))).to.equal(100_000n);
  });

  it("IREC-7.1 D1: nộp lại (thiết bị, ngày) đã phát hành → REJECT KEY", async () => {
    const ctx = await loadFixture(ready);
    await submit(ctx, DAY, 600_000n);
    await ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [100_000n]);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("b"), DEVICES[0], DAY, [100_000n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("b"), DEVICES[0], DAY, Reason.KEY);
  });

  it("IREC-7.1 D2: kỳ 7 ngày phủ lên ngày đã phát hành → REJECT KEY, không mint ngày nào", async () => {
    const ctx = await loadFixture(ready);
    for (let d = DAY; d < DAY + 7; d++) await submit(ctx, d, 600_000n);
    await ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY + 3, [100_000n]);
    const whs = Array(7).fill(100_000n);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("d2"), DEVICES[0], DAY, whs))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("d2"), DEVICES[0], DAY + 3, Reason.KEY);
    expect(await ctx.certs.keyUsed(DEVICES[0], DAY)).to.equal(false);
  });

  it("IREC-7.1 D3: issuer thứ hai đăng ký lại mã đã có → revert DuplicateDevice; yêu cầu của nó → NOT_ISSUER",
    async () => {
      const ctx = await loadFixture(ready);
      await expect(ctx.devices.connect(ctx.issuerB).registerDevice(DEVICES[0], CP, DEVICE_CAP_W, DAY - 30, false, 1))
        .to.be.revertedWithCustomError(ctx.devices, "DuplicateDevice");
      await submit(ctx, DAY, 600_000n);
      await expect(ctx.gate.connect(ctx.issuerB).issue(reqId("d3"), DEVICES[0], DAY, [100_000n]))
        .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("d3"), DEVICES[0], DAY, Reason.NOT_ISSUER);
    });

  it("IREC-7.6 D4b: ví dụ của proposal – đã phát hành 5,0 MWh tại CP-1, thiết bị X xin thêm 1,67 MWh → BUDGET",
    async () => {
      const ctx = await loadFixture(ready);
      await submit(ctx, DAY, 5_000_000n, { sunSlots: 60 });
      for (let i = 0; i < 6; i++) {
        const wh = i < 5 ? 833_333n : 833_335n;
        await ctx.gate.connect(ctx.issuerA).issue(reqId(`h${i}`), DEVICES[i], DAY, [wh]);
      }
      expect(await ctx.certs.issuedWh(CP, DAY)).to.equal(5_000_000n);
      const x = id("X-D4b");
      await ctx.devices.connect(ctx.issuerB).registerDevice(x, CP, 240_000n, DAY, false, 1);
      await expect(ctx.gate.connect(ctx.issuerB).issue(reqId("x"), x, DAY, [1_666_667n]))
        .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("x"), x, DAY, Reason.BUDGET);
    });

  it("IREC-7.6 D4a / D5: tổng yêu cầu vượt O1 của CP → yêu cầu vượt bị REJECT BUDGET", async () => {
    const ctx = await loadFixture(ready);
    await submit(ctx, DAY, 300_000n);
    await ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [200_000n]);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("b"), DEVICES[1], DAY, [100_001n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("b"), DEVICES[1], DAY, Reason.BUDGET);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("c"), DEVICES[1], DAY, [100_000n]))
      .to.emit(ctx.gate, "Issued");
  });

  it("IREC-8.5: O1 khác với O1 đã lưu cho cùng (CP, ngày) → O1Conflict, ngân sách giữ theo O1 đầu tiên", async () => {
    const ctx = await loadFixture(ready);
    await submit(ctx, DAY, 300_000n);
    await expect(submit(ctx, DAY, 900_000n)).to.emit(ctx.gate, "O1Conflict")
      .withArgs(await ctx.gate.lotKeyOf(CP, DAY), 300_000n, 900_000n);
    expect(await ctx.certs.o1Wh(CP, DAY)).to.equal(300_000n);
    await expect(submit(ctx, DAY, 300_000n)).to.be.revertedWithCustomError(ctx.gate, "LotAlreadyEvidenced");
  });

  it("Yêu cầu cho ngày chưa có bằng chứng của lô → REJECT ORACLE", async () => {
    const ctx = await loadFixture(ready);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [100_000n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("a"), DEVICES[0], DAY, Reason.ORACLE);
  });

  it("Luật công suất ③: vượt công suất thiết bị × giờ nắng, hoặc slot O1 vượt công suất CP → CAPACITY", async () => {
    const ctx = await loadFixture(ready);
    await submit(ctx, DAY, 4_000_000n);
    const limit = (DEVICE_CAP_W * BigInt(SUN_SLOTS)) / 4n; // 1,2 MWh
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [limit + 1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("a"), DEVICES[0], DAY, Reason.CAPACITY);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("b"), DEVICES[0], DAY, [limit])).to.emit(ctx.gate, "Issued");

    const reps = reportsFor(DAY + 1, 1_000_000n, 180_001n); // slot lớn nhất vượt 720 kW × 0,25 h
    const e = await evidence(ctx, reps);
    await ctx.gate.connect(ctx.issuerA).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("c"), DEVICES[0], DAY + 1, [10n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("c"), DEVICES[0], DAY + 1, Reason.CAPACITY);
  });

  it("Thiết bị chưa đăng ký → NOT_REGISTERED; người gửi ngoài allowlist issuer → revert", async () => {
    const ctx = await loadFixture(ready);
    await submit(ctx, DAY, 300_000n);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), id("ZZ"), DAY, [1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("a"), id("ZZ"), DAY, Reason.NOT_REGISTERED);
    await expect(ctx.gate.connect(ctx.outsider).issue(reqId("b"), DEVICES[0], DAY, [1n]))
      .to.be.revertedWithCustomError(ctx.gate, "NotIssuer");
  });
});
