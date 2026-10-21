import { expect } from "chai";
import { loadFixture } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { CP, DAY, DEVICES, Reason, deploy, registerAll, reqId, submit, tokenId } from "./fixture";

// Chuyển nhượng, retire (FLOW.md mục 7), Code Manager (mục 6; I-REC §11) và kịch bản insider.
describe("CertificateRegistry – vòng đời và Code Manager", () => {
  async function minted() {
    const ctx = await deploy();
    await registerAll(ctx);
    await submit(ctx, DAY, 600_000n);
    await ctx.gate.connect(ctx.issuerA).issue(reqId("a"), DEVICES[0], DAY, [100_000n]);
    return { ...ctx, tid: tokenId(DEVICES[0], DAY) };
  }
  const retireArgs = ["buyer1 (ESG)", "Scope 2", "California, US", "2022"] as const;

  it("IREC-9.3: người giữ chuyển nhượng được, nhiều lần", async () => {
    const ctx = await loadFixture(minted);
    await ctx.certs.connect(ctx.plant).safeTransferFrom(ctx.plant.address, ctx.buyer1.address, ctx.tid, 60_000n, "0x");
    await ctx.certs.connect(ctx.buyer1).safeTransferFrom(ctx.buyer1.address, ctx.buyer2.address, ctx.tid, 10_000n, "0x");
    expect(await ctx.certs.balanceOf(ctx.buyer1.address, ctx.tid)).to.equal(50_000n);
    expect(await ctx.certs.balanceOf(ctx.buyer2.address, ctx.tid)).to.equal(10_000n);
  });

  it("IREC-10: retire đốt chứng chỉ và ghi đủ người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo", async () => {
    const ctx = await loadFixture(minted);
    await ctx.certs.connect(ctx.plant).safeTransferFrom(ctx.plant.address, ctx.buyer1.address, ctx.tid, 100_000n, "0x");
    await expect(ctx.certs.connect(ctx.buyer1).retire(ctx.tid, 100_000n, ...retireArgs))
      .to.emit(ctx.certs, "Retired").withArgs(ctx.tid, ctx.buyer1.address, 100_000n, ...retireArgs);
    expect(await ctx.certs["totalSupply(uint256)"](ctx.tid)).to.equal(0n);
    expect((await ctx.certs.infoOf(ctx.tid)).retiredWh).to.equal(100_000n);
  });

  it("IREC-10 D6: retire lần hai và chuyển nhượng sau retire đều revert", async () => {
    const ctx = await loadFixture(minted);
    await ctx.certs.connect(ctx.plant).retire(ctx.tid, 100_000n, ...retireArgs);
    await expect(ctx.certs.connect(ctx.plant).retire(ctx.tid, 100_000n, ...retireArgs))
      .to.be.revertedWithCustomError(ctx.certs, "ERC1155InsufficientBalance");
    await expect(ctx.certs.connect(ctx.plant).safeTransferFrom(ctx.plant.address, ctx.buyer1.address, ctx.tid, 1n, "0x"))
      .to.be.revertedWithCustomError(ctx.certs, "ERC1155InsufficientBalance");
  });

  it("IREC-10: retire thiếu trường thông tin → revert EmptyField", async () => {
    const ctx = await loadFixture(minted);
    await expect(ctx.certs.connect(ctx.plant).retire(ctx.tid, 1n, "", "Scope 2", "California, US", "2022"))
      .to.be.revertedWithCustomError(ctx.certs, "EmptyField");
  });

  it("IREC-11: tạm khóa chặn chuyển nhượng và retire; mở khóa thì dùng lại được; mọi thao tác phát event", async () => {
    const ctx = await loadFixture(minted);
    await expect(ctx.certs.connect(ctx.codeManager).suspend(ctx.tid, true, "nghi khai khống"))
      .to.emit(ctx.certs, "Suspended").withArgs(ctx.tid, true, "nghi khai khống");
    await expect(ctx.certs.connect(ctx.plant).safeTransferFrom(ctx.plant.address, ctx.buyer1.address, ctx.tid, 1n, "0x"))
      .to.be.revertedWithCustomError(ctx.certs, "TokenSuspended");
    await expect(ctx.certs.connect(ctx.plant).retire(ctx.tid, 1n, ...retireArgs))
      .to.be.revertedWithCustomError(ctx.certs, "TokenSuspended");
    await ctx.certs.connect(ctx.codeManager).suspend(ctx.tid, false, "điều tra xong, hợp lệ");
    await ctx.certs.connect(ctx.plant).safeTransferFrom(ctx.plant.address, ctx.buyer1.address, ctx.tid, 1n, "0x");
  });

  it("IREC-11: rút chứng chỉ chưa retire trả lại ngân sách CP và mở lại khóa để phát hành lại đúng", async () => {
    const ctx = await loadFixture(minted);
    await expect(ctx.certs.connect(ctx.codeManager).withdraw(ctx.tid, ctx.plant.address, 100_000n, "phát hiện khai khống"))
      .to.emit(ctx.certs, "Withdrawn").withArgs(ctx.tid, ctx.plant.address, 100_000n, "phát hiện khai khống");
    expect(await ctx.certs.issuedWh(CP, DAY)).to.equal(0n);
    expect(await ctx.certs.keyUsed(DEVICES[0], DAY)).to.equal(false);
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("again"), DEVICES[0], DAY, [80_000n]))
      .to.emit(ctx.gate, "Issued");
  });

  it("IREC-11: rút một phần thì khóa vẫn đóng; phần đã retire không rút được", async () => {
    const ctx = await loadFixture(minted);
    await ctx.certs.connect(ctx.plant).retire(ctx.tid, 30_000n, ...retireArgs);
    await ctx.certs.connect(ctx.codeManager).withdraw(ctx.tid, ctx.plant.address, 70_000n, "khai khống");
    expect(await ctx.certs.issuedWh(CP, DAY)).to.equal(30_000n);
    expect(await ctx.certs.keyUsed(DEVICES[0], DAY)).to.equal(true); // đã có tuyên bố retire nên không mở lại
    await expect(ctx.certs.connect(ctx.codeManager).withdraw(ctx.tid, ctx.plant.address, 1n, "khai khống"))
      .to.be.revertedWithCustomError(ctx.certs, "ERC1155InsufficientBalance");
    await expect(ctx.gate.connect(ctx.issuerA).issue(reqId("again"), DEVICES[0], DAY, [1n]))
      .to.emit(ctx.gate, "IssueRejected").withArgs(reqId("again"), DEVICES[0], DAY, Reason.KEY);
  });

  it("IREC-11: chỉ Code Manager tạm khóa / rút được; Code Manager không mint được", async () => {
    const ctx = await loadFixture(minted);
    for (const who of [ctx.issuerA, ctx.auditor, ctx.plant]) {
      await expect(ctx.certs.connect(who).suspend(ctx.tid, true, "x")).to.be.revertedWithCustomError(ctx.certs,
        "NotCodeManager");
      await expect(ctx.certs.connect(who).withdraw(ctx.tid, ctx.plant.address, 1n, "x"))
        .to.be.revertedWithCustomError(ctx.certs, "NotCodeManager");
    }
    await expect(ctx.certs.connect(ctx.codeManager).mint(ctx.codeManager.address, DEVICES[1], CP, DAY, 1n))
      .to.be.revertedWithCustomError(ctx.certs, "NotGate");
    await expect(ctx.certs.connect(ctx.codeManager).suspend(ctx.tid, true, ""))
      .to.be.revertedWithCustomError(ctx.certs, "EmptyField");
  });

  it("Insider: không có hàm sửa, xóa hay phát hành lại; gate chỉ đặt được một lần", async () => {
    const ctx = await loadFixture(minted);
    const fns = [ctx.certs, ctx.gate, ctx.devices].flatMap((c) => c.interface.fragments
      .filter((f) => f.type === "function").map((f) => (f as { name: string }).name));
    for (const banned of ["update", "edit", "delete", "remove", "reissue", "setBalance", "adminMint", "upgradeTo"]) {
      expect(fns.some((n) => n.toLowerCase().includes(banned.toLowerCase())), banned).to.equal(false);
    }
    await expect(ctx.certs.setGate(ctx.outsider.address)).to.be.revertedWithCustomError(ctx.certs, "GateAlreadySet");
    await expect(ctx.certs.connect(ctx.issuerA).mint(ctx.issuerA.address, DEVICES[1], CP, DAY, 1n))
      .to.be.revertedWithCustomError(ctx.certs, "NotGate");
  });
});
