import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { CP, DAY, DEVICES, Flag, Reason, Status, deploy, evidence, registerAll, reportsFor, reqId, structHash, submit }
  from "./fixture";

// Nhánh REVIEW (FLOW.md mục 5) và kiểm tra chữ ký EIP-712 của bằng chứng (FLOW.md mục 3).
describe("DecisionGate – REVIEW và chữ ký", () => {
  async function ready() {
    const ctx = await deploy();
    await registerAll(ctx);
    return ctx;
  }

  it("IREC-8.7: lô có cờ → LotReview; yêu cầu của lô bị giữ (IssueHeld), không mint", async () => {
    const ctx = await loadFixture(ready);
    const key = await ctx.gate.lotKeyOf(CP, DAY);
    await expect(submit(ctx, DAY, 600_000n, { flags: Flag.OVER_CEILING })).to.emit(ctx.gate, "LotReview")
      .withArgs(key, Flag.OVER_CEILING, ethers.ZeroHash);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [100_000n]))
      .to.emit(ctx.gate, "IssueHeld").withArgs(reqId("a"), key);
    expect(await ctx.certs.keyUsed(DEVICES[0], DAY)).to.equal(false);
    expect((await ctx.gate.lotState(key)).status).to.equal(Status.REVIEW);
  });

  it("IREC-8.5 / IREC-8.7: auditor duyệt → issuer gửi lại và được MINT", async () => {
    const ctx = await loadFixture(ready);
    const key = await ctx.gate.lotKeyOf(CP, DAY);
    await submit(ctx, DAY, 600_000n, { flags: Flag.INCONSISTENT });
    const why = ethers.keccak256(ethers.toUtf8Bytes("đã đối chiếu hóa đơn điện lực"));
    await expect(ctx.gate.connect(ctx.auditor).resolveReview(key, true, why)).to.emit(ctx.gate, "LotResolved")
      .withArgs(key, true, ctx.auditor.address, why);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [100_000n])).to.emit(ctx.gate, "Issued");
  });

  it("IREC-8.7: auditor bác → mọi yêu cầu của lô bị REJECT LOT_REJECTED", async () => {
    const ctx = await loadFixture(ready);
    const key = await ctx.gate.lotKeyOf(CP, DAY);
    await submit(ctx, DAY, 600_000n, { flags: Flag.INCONSISTENT });
    await ctx.gate.connect(ctx.auditor).resolveReview(key, false, ethers.ZeroHash);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [100_000n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("a"), DEVICES[0], DAY, Reason.LOT_REJECTED);
  });

  it("IREC-8.7: chỉ khóa auditor gọi được resolveReview, và chỉ với lô đang REVIEW", async () => {
    const ctx = await loadFixture(ready);
    const key = await ctx.gate.lotKeyOf(CP, DAY);
    await submit(ctx, DAY, 600_000n, { flags: Flag.MISSING_REPORT });
    for (const who of [ctx.issuerA, ctx.codeManager, ctx.verifier]) {
      await expect(ctx.gate.connect(who).resolveReview(key, true, ethers.ZeroHash))
        .to.be.revertedWithCustomError(ctx.gate, "NotAuditor");
    }
    await ctx.gate.connect(ctx.auditor).resolveReview(key, true, ethers.ZeroHash);
    await expect(ctx.gate.connect(ctx.auditor).resolveReview(key, false, ethers.ZeroHash))
      .to.be.revertedWithCustomError(ctx.gate, "NotUnderReview");
  });

  it("Báo cáo ký bằng khóa không thuộc allowlist của (oracle, CP) → revert BadSignature", async () => {
    const ctx = await loadFixture(ready);
    const forged = [ctx.outsider, ...ctx.oracles.slice(1)];
    const e = await evidence(ctx, reportsFor(DAY, 600_000n), { signers: forged });
    await expect(ctx.gate.connect(ctx.issuerA).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig))
      .to.be.revertedWithCustomError(ctx.gate, "BadSignature").withArgs(0);
  });

  it("Báo cáo bị sửa sau khi ký → revert BadSignature", async () => {
    const ctx = await loadFixture(ready);
    const e = await evidence(ctx, reportsFor(DAY, 600_000n));
    const tampered = e.reports.map((r, i) => (i === 0 ? { ...r, valueDay: 900_000n } : r));
    await expect(ctx.gate.connect(ctx.issuerA).submitLotEvidence(tampered, e.sigs, e.verdict, e.vsig))
      .to.be.revertedWithCustomError(ctx.gate, "BadSignature").withArgs(0);
  });

  it("Verdict ký bởi khóa không phải verifier → revert; verdict không khớp 4 báo cáo → revert BadVerdict", async () => {
    const ctx = await loadFixture(ready);
    let e = await evidence(ctx, reportsFor(DAY, 600_000n), { verifier: ctx.issuerA });
    await expect(ctx.gate.connect(ctx.issuerA).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig))
      .to.be.revertedWithCustomError(ctx.gate, "BadSignature").withArgs(4);
    e = await evidence(ctx, reportsFor(DAY, 600_000n), { reportsHash: structHash(reportsFor(DAY, 1n)[0]) });
    await expect(ctx.gate.connect(ctx.issuerA).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig))
      .to.be.revertedWithCustomError(ctx.gate, "BadVerdict");
  });

  it("Thiếu báo cáo O2–O4 vẫn gửi được (verdict mang cờ MISSING_REPORT); thiếu O1 → revert", async () => {
    const ctx = await loadFixture(ready);
    const reps = reportsFor(DAY, 600_000n);
    reps[2] = { ...reps[2], oracle: 0 };
    const e = await evidence(ctx, reps, { flags: Flag.MISSING_REPORT });
    await expect(ctx.gate.connect(ctx.issuerA).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig))
      .to.emit(ctx.gate, "LotReview");
    const reps2 = reportsFor(DAY + 1, 600_000n);
    reps2[0] = { ...reps2[0], oracle: 0 };
    const e2 = await evidence(ctx, reps2);
    await expect(ctx.gate.connect(ctx.issuerA).submitLotEvidence(e2.reports, e2.sigs, e2.verdict, e2.vsig))
      .to.be.revertedWithCustomError(ctx.gate, "BadReport").withArgs(0);
  });

  it("Chỉ issuer trong allowlist gửi được bằng chứng của lô", async () => {
    const ctx = await loadFixture(ready);
    const e = await evidence(ctx, reportsFor(DAY, 600_000n));
    await expect(ctx.gate.connect(ctx.outsider).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig))
      .to.be.revertedWithCustomError(ctx.gate, "NotIssuer");
  });
});
