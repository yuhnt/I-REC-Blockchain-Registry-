// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {DeviceRegistry} from "./DeviceRegistry.sol";
import {CertificateRegistry} from "./CertificateRegistry.sol";

/// @title DecisionGate – nhận bằng chứng của lô và quyết định phát hành (FLOW.md mục 4–5).
/// @notice Hai bước: `submitLotEvidence` một lần mỗi lô (4 báo cáo oracle + verdict của lớp B, có chữ ký EIP-712);
/// `issue` cho từng thiết bị: đăng ký → kỳ phát hành (§8.2) → ① khóa → ② ngân sách → ③ công suất → trạng thái lô.
/// Vi phạm lớp A không revert mà phát `IssueRejected` kèm mã lý do, để lý do được lưu công khai (§8.7).
contract DecisionGate is EIP712 {
    /// Khớp rec.schema.RejectReason theo thứ tự.
    enum Reason { KEY, BUDGET, CAPACITY, PERIOD, ORACLE, LOT_REJECTED, NOT_ISSUER, NOT_REGISTERED }
    enum Status { NONE, CLEAR, REVIEW, APPROVED, REJECTED }

    struct OracleReport {
        uint8 oracle; // 1..4 = O1..O4; 0 = thiếu báo cáo (O1 không được thiếu)
        bytes32 cpId;
        uint32 day;
        uint64 valueDay;
        uint64 maxSlot;
        uint16 slotsPresent;
        bytes32 dataRoot;
    }

    struct Verdict {
        bytes32 lotKey;
        uint8 flags;
        uint64 ceilingWh;
        uint16 sunSlots;
        bytes32 reportsHash;
        bytes32 modelHash;
        bytes32 reasonsHash;
    }

    struct Lot {
        uint64 o1Wh;
        uint64 maxSlot;
        uint16 sunSlots;
        uint8 flags;
        Status status;
    }

    bytes32 public constant REPORT_TYPEHASH = keccak256(
        "OracleReport(uint8 oracle,bytes32 cpId,uint32 day,uint64 valueDay,uint64 maxSlot,uint16 slotsPresent,bytes32 dataRoot)");
    bytes32 public constant VERDICT_TYPEHASH = keccak256(
        "Verdict(bytes32 lotKey,uint8 flags,uint64 ceilingWh,uint16 sunSlots,bytes32 reportsHash,bytes32 modelHash,bytes32 reasonsHash)");
    /// Ngày địa phương d được coi là đã kết thúc từ (d + 1) · 86400 + 7 h theo UTC, tức 00:00 PDT ngày d + 1.
    /// Mùa đông (PST) mốc này sớm hơn nửa đêm thật 1 giờ; đơn giản hóa vì contract không biết giờ mùa hè.
    uint256 public constant DAY_END_OFFSET_S = 7 hours;
    uint256 private constant SLOTS_PER_HOUR = 4;

    DeviceRegistry public immutable devices;
    CertificateRegistry public immutable certificates;
    address public immutable auditor;
    mapping(bytes32 => mapping(uint8 => address)) public oracleSigner; // (CP, oracle) → khóa được phép
    mapping(address => bool) public isVerifier;
    mapping(bytes32 => address) public holderOf; // CP → địa chỉ nhận chứng chỉ (nhà máy)
    mapping(bytes32 => Lot) private _lots;

    event LotEvidenced(bytes32 indexed lotKey, bytes32 indexed cpId, uint32 day, uint64 o1Wh, uint8 flags,
        bytes32 verdictHash, bytes32[4] dataRoots);
    event LotReview(bytes32 indexed lotKey, uint8 flags, bytes32 reasonsHash);
    event LotResolved(bytes32 indexed lotKey, bool approved, address auditor, bytes32 reasonHash);
    event O1Conflict(bytes32 indexed lotKey, uint64 storedWh, uint64 offeredWh);
    event Issued(bytes32 indexed reqId, uint256 indexed tokenId, bytes32 indexed deviceId, uint32 day, uint64 wh,
        address to);
    event IssueRejected(bytes32 indexed reqId, bytes32 indexed deviceId, uint32 day, Reason reason);
    event IssueHeld(bytes32 indexed reqId, bytes32 lotKey);

    error NotIssuer();
    error NotAuditor();
    error BadReport(uint256 index);
    error BadSignature(uint256 index);
    error BadVerdict();
    error LotAlreadyEvidenced(bytes32 lotKey);
    error NotUnderReview(bytes32 lotKey);
    error EmptyRequest();

    constructor(DeviceRegistry devices_, CertificateRegistry certificates_, address auditor_, bytes32[] memory cpIds,
        address[] memory holders, address[4][] memory signers, address[] memory verifiers) EIP712("REC-A5", "1") {
        require(cpIds.length == holders.length && cpIds.length == signers.length, "cp length");
        devices = devices_;
        certificates = certificates_;
        auditor = auditor_;
        for (uint256 i = 0; i < cpIds.length; i++) {
            holderOf[cpIds[i]] = holders[i];
            for (uint8 o = 0; o < 4; o++) oracleSigner[cpIds[i]][o + 1] = signers[i][o];
        }
        for (uint256 i = 0; i < verifiers.length; i++) isVerifier[verifiers[i]] = true;
    }

    modifier onlyIssuer() {
        if (!devices.isIssuer(msg.sender)) revert NotIssuer();
        _;
    }

    // ------------------------------------------------------------------ bằng chứng của lô

    function lotKeyOf(bytes32 cpId, uint32 day) public pure returns (bytes32) {
        return keccak256(abi.encode(cpId, day));
    }

    function reportHash(OracleReport calldata r) public pure returns (bytes32) {
        if (r.oracle == 0) return bytes32(0);
        return keccak256(abi.encode(REPORT_TYPEHASH, r.oracle, r.cpId, r.day, r.valueDay, r.maxSlot, r.slotsPresent,
            r.dataRoot));
    }

    function verdictHash(Verdict calldata v) public pure returns (bytes32) {
        return keccak256(abi.encode(VERDICT_TYPEHASH, v.lotKey, v.flags, v.ceilingWh, v.sunSlots, v.reportsHash,
            v.modelHash, v.reasonsHash));
    }

    /// @notice Gửi bằng chứng của một lô. O1 của (CP, ngày) được lưu ở lần đầu; O1 khác gửi sau bị từ chối và
    /// phát `O1Conflict` (trả false, không revert, để sự kiện còn lại on-chain).
    function submitLotEvidence(OracleReport[4] calldata reports, bytes[4] calldata reportSigs, Verdict calldata verdict,
        bytes calldata verdictSig) external onlyIssuer returns (bool accepted) {
        bytes32 cpId = reports[0].cpId;
        uint32 day = reports[0].day;
        bytes32[4] memory hashes;
        bytes32[4] memory roots;
        for (uint8 i = 0; i < 4; i++) {
            OracleReport calldata r = reports[i];
            if (r.oracle == 0) {
                if (i == 0) revert BadReport(i); // O1 là cơ sở của ngân sách CP, không được thiếu
                continue;
            }
            if (r.oracle != i + 1 || r.cpId != cpId || r.day != day || r.maxSlot > r.valueDay) revert BadReport(i);
            hashes[i] = reportHash(r);
            roots[i] = r.dataRoot;
            if (ECDSA.recover(_hashTypedDataV4(hashes[i]), reportSigs[i]) != oracleSigner[cpId][r.oracle]) {
                revert BadSignature(i);
            }
        }
        bytes32 key = lotKeyOf(cpId, day);
        if (verdict.lotKey != key || verdict.reportsHash != keccak256(abi.encode(hashes))) revert BadVerdict();
        bytes32 vHash = verdictHash(verdict);
        if (!isVerifier[ECDSA.recover(_hashTypedDataV4(vHash), verdictSig)]) revert BadSignature(4);

        Lot storage lot = _lots[key];
        uint64 o1 = reports[0].valueDay;
        if (lot.status != Status.NONE) {
            if (lot.o1Wh != o1) {
                emit O1Conflict(key, lot.o1Wh, o1);
                return false;
            }
            revert LotAlreadyEvidenced(key);
        }
        lot.o1Wh = o1;
        lot.maxSlot = reports[0].maxSlot;
        lot.sunSlots = verdict.sunSlots;
        lot.flags = verdict.flags;
        lot.status = verdict.flags == 0 ? Status.CLEAR : Status.REVIEW;
        certificates.recordO1(cpId, day, o1);
        emit LotEvidenced(key, cpId, day, o1, verdict.flags, vHash, roots);
        if (verdict.flags != 0) emit LotReview(key, verdict.flags, verdict.reasonsHash);
        return true;
    }

    /// @notice Production Auditor phân xử lô REVIEW (cách B). Chỉ đổi trạng thái lô, không mint.
    function resolveReview(bytes32 lotKey, bool approve, bytes32 reasonHash) external {
        if (msg.sender != auditor) revert NotAuditor();
        Lot storage lot = _lots[lotKey];
        if (lot.status != Status.REVIEW) revert NotUnderReview(lotKey);
        lot.status = approve ? Status.APPROVED : Status.REJECTED;
        emit LotResolved(lotKey, approve, msg.sender, reasonHash);
    }

    function lotState(bytes32 lotKey) external view returns (uint64 o1Wh, uint64 maxSlot, uint16 sunSlots, uint8 flags,
        Status status) {
        Lot storage l = _lots[lotKey];
        return (l.o1Wh, l.maxSlot, l.sunSlots, l.flags, l.status);
    }

    // ------------------------------------------------------------------ phát hành

    /// @notice Yêu cầu phát hành cho một thiết bị, kỳ gồm `whPerDay.length` ngày liên tiếp từ `dayStart`.
    /// Chỉ cần một ngày vi phạm là cả yêu cầu bị từ chối. Ngày có lượng 0 được bỏ qua.
    /// @return outcome 0 = từ chối, 1 = đã mint, 2 = giữ lại vì lô đang REVIEW.
    function issue(bytes32 reqId, bytes32 deviceId, uint32 dayStart, uint64[] calldata whPerDay) external onlyIssuer
        returns (uint8 outcome) {
        uint256 n = whPerDay.length;
        if (n == 0) revert EmptyRequest();
        uint32 dayEnd = dayStart + uint32(n) - 1;
        if (!devices.exists(deviceId)) return _reject(reqId, deviceId, dayStart, Reason.NOT_REGISTERED);
        (bytes32 cpId,, uint64 capW, uint32 effectiveDay, uint32 endDay,) = devices.deviceOf(deviceId);

        // Kỳ phát hành (§8.2): trọn một năm dương lịch (nên ≤ 1 năm), không trước ngày đăng ký hiệu lực,
        // không từ ngày đóng đăng ký, và đã kết thúc trước thời điểm nộp.
        if (yearOf(dayStart) != yearOf(dayEnd) || dayStart < effectiveDay || dayEnd >= endDay
            || block.timestamp < (uint256(dayEnd) + 1) * 1 days + DAY_END_OFFSET_S) {
            return _reject(reqId, deviceId, dayStart, Reason.PERIOD);
        }
        // Người gửi phải là issuer phụ trách thiết bị ở mọi ngày trong kỳ (§16.3).
        for (uint32 d = dayStart; d <= dayEnd; d++) {
            if (devices.issuerOn(deviceId, d) != msg.sender) return _reject(reqId, deviceId, d, Reason.NOT_ISSUER);
        }

        uint256 cpCap = devices.cpCapacityW(cpId);
        bytes32 heldLot;
        for (uint256 i = 0; i < n; i++) {
            uint64 wh = whPerDay[i];
            if (wh == 0) continue;
            uint32 d = dayStart + uint32(i);
            if (certificates.keyUsed(deviceId, d)) return _reject(reqId, deviceId, d, Reason.KEY);
            bytes32 key = lotKeyOf(cpId, d);
            Lot storage lot = _lots[key];
            if (lot.status == Status.NONE) return _reject(reqId, deviceId, d, Reason.ORACLE);
            if (certificates.issuedWh(cpId, d) + wh > lot.o1Wh) return _reject(reqId, deviceId, d, Reason.BUDGET);
            if (uint256(wh) * SLOTS_PER_HOUR > uint256(capW) * lot.sunSlots
                || uint256(lot.maxSlot) * SLOTS_PER_HOUR > cpCap
                || uint256(lot.o1Wh) * SLOTS_PER_HOUR > cpCap * lot.sunSlots) {
                return _reject(reqId, deviceId, d, Reason.CAPACITY);
            }
            if (lot.status == Status.REJECTED) return _reject(reqId, deviceId, d, Reason.LOT_REJECTED);
            if (lot.status == Status.REVIEW && heldLot == bytes32(0)) heldLot = key;
        }
        if (heldLot != bytes32(0)) {
            emit IssueHeld(reqId, heldLot);
            return 2;
        }
        address to = holderOf[cpId];
        for (uint256 i = 0; i < n; i++) {
            if (whPerDay[i] == 0) continue;
            uint32 d = dayStart + uint32(i);
            uint256 tokenId = certificates.mint(to, deviceId, cpId, d, whPerDay[i]);
            emit Issued(reqId, tokenId, deviceId, d, whPerDay[i], to);
        }
        return 1;
    }

    function _reject(bytes32 reqId, bytes32 deviceId, uint32 day, Reason reason) private returns (uint8) {
        emit IssueRejected(reqId, deviceId, day, reason);
        return 0;
    }

    /// Năm dương lịch của số ngày kể từ 1970-01-01 (thuật toán civil_from_days của H. Hinnant).
    function yearOf(uint32 day) public pure returns (uint256) {
        uint256 z = uint256(day) + 719468;
        uint256 era = z / 146097;
        uint256 doe = z - era * 146097;
        uint256 yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
        uint256 doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
        uint256 mp = (5 * doy + 2) / 153;
        return yoe + era * 400 + (mp >= 10 ? 1 : 0);
    }
}
