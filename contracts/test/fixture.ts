import { ethers } from "hardhat";
import type { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import type { CertificateRegistry, DecisionGate, DeviceRegistry } from "../typechain-types";

// Dữ liệu chung của các test: một CP 720 kW, 6 thiết bị 120 kW (SPEC mục 3), ngày 19000 = 08/01/2022.
export const CP = ethers.encodeBytes32String("CP-1");
export const CP_CAP_W = 720_000n;
export const DEVICE_CAP_W = 120_000n;
export const DAY = 19000;
export const SUN_SLOTS = 40; // 10 giờ có nắng
export const Reason = { KEY: 0n, BUDGET: 1n, CAPACITY: 2n, PERIOD: 3n, ORACLE: 4n, LOT_REJECTED: 5n, NOT_ISSUER: 6n,
  NOT_REGISTERED: 7n };
export const Status = { NONE: 0n, CLEAR: 1n, REVIEW: 2n, APPROVED: 3n, REJECTED: 4n };
export const Flag = { INCONSISTENT: 1, MISSING_REPORT: 2, OVER_CEILING: 4 };

export const id = (s: string) => ethers.encodeBytes32String(s);
export const DEVICES = ["B1", "B2", "B3", "B4", "B5", "B6"].map(id);

const REPORT_TYPES = {
  OracleReport: [
    { name: "oracle", type: "uint8" }, { name: "cpId", type: "bytes32" }, { name: "day", type: "uint32" },
    { name: "valueDay", type: "uint64" }, { name: "maxSlot", type: "uint64" }, { name: "slotsPresent", type: "uint16" },
    { name: "dataRoot", type: "bytes32" },
  ],
};
const VERDICT_TYPES = {
  Verdict: [
    { name: "lotKey", type: "bytes32" }, { name: "flags", type: "uint8" }, { name: "ceilingWh", type: "uint64" },
    { name: "sunSlots", type: "uint16" }, { name: "reportsHash", type: "bytes32" }, { name: "modelHash", type: "bytes32" },
    { name: "reasonsHash", type: "bytes32" },
  ],
};

export type Report = { oracle: number; cpId: string; day: number; valueDay: bigint; maxSlot: bigint;
  slotsPresent: number; dataRoot: string };

export async function deploy() {
  const s = await ethers.getSigners();
  const [deployer, issuerA, issuerB, o1, o2, o3, o4, verifier, auditor, codeManager, plant, buyer1, buyer2, outsider] = s;
  const devices = (await ethers.deployContract("DeviceRegistry", [[issuerA.address, issuerB.address], [CP],
    [CP_CAP_W]])) as unknown as DeviceRegistry;
  const certs = (await ethers.deployContract("CertificateRegistry", [codeManager.address])) as unknown as
    CertificateRegistry;
  const gate = (await ethers.deployContract("DecisionGate", [await devices.getAddress(), await certs.getAddress(),
    auditor.address, [CP], [plant.address], [[o1.address, o2.address, o3.address, o4.address]], [verifier.address]])) as
    unknown as DecisionGate;
  await certs.setGate(await gate.getAddress());
  const domain = { name: "REC-A5", version: "1", chainId: 31337, verifyingContract: await gate.getAddress() };
  return { deployer, issuerA, issuerB, oracles: [o1, o2, o3, o4], verifier, auditor, codeManager, plant, buyer1,
    buyer2, outsider, devices, certs, gate, domain };
}

export type Ctx = Awaited<ReturnType<typeof deploy>>;

export async function registerAll(ctx: Ctx, effectiveDay = DAY - 30) {
  for (const d of DEVICES) {
    await ctx.devices.connect(ctx.issuerA).registerDevice(d, CP, DEVICE_CAP_W, effectiveDay, false, 1);
  }
}

export function reportsFor(day: number, o1Wh: bigint, maxSlot = o1Wh / 20n): Report[] {
  const root = (i: number) => ethers.keccak256(ethers.toUtf8Bytes(`${day}-${i}`));
  const base = { cpId: CP, day, slotsPresent: SUN_SLOTS };
  return [
    { ...base, oracle: 1, valueDay: o1Wh, maxSlot, dataRoot: root(1) },
    { ...base, oracle: 2, valueDay: (o1Wh * 1017n) / 1000n, maxSlot, dataRoot: root(2) },
    { ...base, oracle: 3, valueDay: 6_000n, maxSlot: 900n, dataRoot: root(3) },
    { ...base, oracle: 4, valueDay: 6_300n, maxSlot: 950n, dataRoot: root(4) },
  ];
}

export function structHash(r: Report): string {
  return ethers.TypedDataEncoder.hashStruct("OracleReport", REPORT_TYPES, r);
}

/// Ký 4 báo cáo bằng khóa oracle (có thể thay khóa để thử chữ ký sai) và ký verdict bằng khóa verifier.
export async function evidence(ctx: Ctx, reports: Report[], opts: { flags?: number; signers?: HardhatEthersSigner[];
  verifier?: HardhatEthersSigner; sunSlots?: number; reportsHash?: string } = {}) {
  const signers = opts.signers ?? ctx.oracles;
  const sigs = await Promise.all(reports.map((r, i) => signers[i].signTypedData(ctx.domain, REPORT_TYPES, r)));
  const hashes = reports.map((r) => (r.oracle === 0 ? ethers.ZeroHash : structHash(r)));
  const verdict = {
    lotKey: await ctx.gate.lotKeyOf(reports[0].cpId, reports[0].day),
    flags: opts.flags ?? 0,
    ceilingWh: 0n,
    sunSlots: opts.sunSlots ?? SUN_SLOTS,
    reportsHash: opts.reportsHash ??
      ethers.keccak256(ethers.AbiCoder.defaultAbiCoder().encode(["bytes32[4]"], [hashes])),
    modelHash: ethers.keccak256(ethers.toUtf8Bytes("B1")),
    reasonsHash: ethers.ZeroHash,
  };
  const vsig = await (opts.verifier ?? ctx.verifier).signTypedData(ctx.domain, VERDICT_TYPES, verdict);
  return { reports, sigs, verdict, vsig };
}

export async function submit(ctx: Ctx, day: number, o1Wh: bigint, opts: Parameters<typeof evidence>[2] = {}) {
  const e = await evidence(ctx, reportsFor(day, o1Wh), opts);
  return ctx.gate.connect(ctx.issuerA).submitLotEvidence(e.reports, e.sigs, e.verdict, e.vsig);
}

export function tokenId(device: string, day: number): bigint {
  return BigInt(ethers.keccak256(ethers.AbiCoder.defaultAbiCoder().encode(["bytes32", "uint32"], [device, day])));
}

export const reqId = (s: string) => id(s);
