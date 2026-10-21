// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {ERC1155Supply} from "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Supply.sol";

/// @title CertificateRegistry – chứng chỉ I-REC dạng ERC-1155, đơn vị Wh (FLOW.md mục 9).
/// @notice Bất biến chống double counting nằm ở đây, không nằm ở gate, để gate có lỗi cũng không phát hành trùng:
///  ① khóa (thiết bị, ngày) chỉ phát hành một lần;
///  ② ngân sách: Σ phát hành tại (CP, ngày) ≤ O1 đã lưu lần đầu.
/// Chỉ DecisionGate mint được. Code Manager (I-REC §11) chỉ tạm khóa và rút chứng chỉ chưa retire, luôn phát event.
contract CertificateRegistry is ERC1155Supply {
    struct Info {
        bytes32 deviceId;
        bytes32 cpId;
        uint32 day;
        bool issued; // khóa ① đang đóng
        bool suspended;
        uint64 retiredWh;
    }

    address public immutable deployer;
    address public immutable codeManager;
    address public gate; // đặt đúng một lần sau khi deploy gate, rồi khóa vĩnh viễn

    mapping(uint256 => Info) private _info;
    mapping(bytes32 => mapping(uint32 => uint64)) public o1Wh; // O1 của (CP, ngày), ghi một lần
    mapping(bytes32 => mapping(uint32 => uint64)) public issuedWh; // Σ đã phát hành tại (CP, ngày)

    event Retired(uint256 indexed tokenId, address indexed holder, uint256 wh, string beneficiary, string purpose,
        string consumptionLocation, string reportingPeriod);
    event Suspended(uint256 indexed tokenId, bool active, string reason);
    event Withdrawn(uint256 indexed tokenId, address indexed holder, uint256 wh, string reason);

    error NotGate();
    error NotCodeManager();
    error GateAlreadySet();
    error KeyUsed(uint256 tokenId);
    error OverBudget(bytes32 cpId, uint32 day);
    error O1AlreadyRecorded(bytes32 cpId, uint32 day);
    error UnknownToken(uint256 tokenId);
    error TokenSuspended(uint256 tokenId);
    error EmptyField();

    constructor(address codeManager_) ERC1155("") {
        deployer = msg.sender;
        codeManager = codeManager_;
    }

    function setGate(address gate_) external {
        if (msg.sender != deployer || gate != address(0)) revert GateAlreadySet();
        gate = gate_;
    }

    modifier onlyGate() {
        if (msg.sender != gate) revert NotGate();
        _;
    }

    modifier onlyCodeManager() {
        if (msg.sender != codeManager) revert NotCodeManager();
        _;
    }

    function tokenIdOf(bytes32 deviceId, uint32 day) public pure returns (uint256) {
        return uint256(keccak256(abi.encode(deviceId, day)));
    }

    function recordO1(bytes32 cpId, uint32 day, uint64 wh) external onlyGate {
        if (o1Wh[cpId][day] != 0) revert O1AlreadyRecorded(cpId, day);
        o1Wh[cpId][day] = wh;
    }

    function keyUsed(bytes32 deviceId, uint32 day) external view returns (bool) {
        return _info[tokenIdOf(deviceId, day)].issued;
    }

    function mint(address to, bytes32 deviceId, bytes32 cpId, uint32 day, uint64 wh) external onlyGate
        returns (uint256 tokenId) {
        tokenId = tokenIdOf(deviceId, day);
        Info storage inf = _info[tokenId];
        if (inf.issued) revert KeyUsed(tokenId);
        uint64 total = issuedWh[cpId][day] + wh;
        if (total > o1Wh[cpId][day]) revert OverBudget(cpId, day);
        issuedWh[cpId][day] = total;
        inf.deviceId = deviceId;
        inf.cpId = cpId;
        inf.day = day;
        inf.issued = true;
        _mint(to, tokenId, wh, "");
    }

    /// @notice Redemption (I-REC §10): đốt chứng chỉ của người giữ, ghi tuyên bố; không đảo ngược, không sửa được.
    function retire(uint256 tokenId, uint256 wh, string calldata beneficiary, string calldata purpose,
        string calldata consumptionLocation, string calldata reportingPeriod) external {
        Info storage inf = _info[tokenId];
        if (!inf.issued) revert UnknownToken(tokenId);
        if (inf.suspended) revert TokenSuspended(tokenId);
        if (bytes(beneficiary).length == 0 || bytes(purpose).length == 0 || bytes(consumptionLocation).length == 0
            || bytes(reportingPeriod).length == 0) revert EmptyField();
        _burn(msg.sender, tokenId, wh);
        inf.retiredWh += uint64(wh);
        emit Retired(tokenId, msg.sender, wh, beneficiary, purpose, consumptionLocation, reportingPeriod);
    }

    /// @notice Tạm khóa hoặc mở khóa chứng chỉ chưa retire (I-REC §11). Khi khóa: không chuyển, không retire được.
    function suspend(uint256 tokenId, bool active, string calldata reason) external onlyCodeManager {
        Info storage inf = _info[tokenId];
        if (!inf.issued || totalSupply(tokenId) == 0) revert UnknownToken(tokenId);
        if (bytes(reason).length == 0) revert EmptyField();
        inf.suspended = active;
        emit Suspended(tokenId, active, reason);
    }

    /// @notice Rút chứng chỉ phát hành sai, chỉ phần chưa retire (đã retire thì đã bị đốt, không rút được).
    /// Phần rút trả lại ngân sách CP. Rút hết và chưa từng retire thì mở lại khóa để phát hành lại đúng.
    function withdraw(uint256 tokenId, address holder, uint256 wh, string calldata reason) external onlyCodeManager {
        Info storage inf = _info[tokenId];
        if (!inf.issued) revert UnknownToken(tokenId);
        if (bytes(reason).length == 0) revert EmptyField();
        _burn(holder, tokenId, wh);
        issuedWh[inf.cpId][inf.day] -= uint64(wh);
        if (totalSupply(tokenId) == 0 && inf.retiredWh == 0) {
            inf.issued = false;
            inf.suspended = false;
        }
        emit Withdrawn(tokenId, holder, wh, reason);
    }

    function infoOf(uint256 tokenId) external view returns (Info memory) {
        return _info[tokenId];
    }

    /// Chặn chuyển nhượng khi chứng chỉ đang bị tạm khóa; mint và burn không bị chặn ở đây.
    function _update(address from, address to, uint256[] memory ids, uint256[] memory values) internal override {
        if (from != address(0) && to != address(0)) {
            for (uint256 i = 0; i < ids.length; i++) {
                if (_info[ids[i]].suspended) revert TokenSuspended(ids[i]);
            }
        }
        super._update(from, to, ids, values);
    }
}
