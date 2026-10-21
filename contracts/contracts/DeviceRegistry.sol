// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title DeviceRegistry – sổ đăng ký thiết bị dùng chung cho mọi issuer (FLOW.md mục 8).
/// @notice Mã thiết bị là duy nhất trên toàn sổ cái: issuer thứ hai đăng ký lại mã đã có bị revert (D3).
/// Thiết bị gắn đúng một điểm đấu nối (CP, I-REC §7.6). Chuyển đăng ký giữ nguyên mã (§16.3).
/// Allowlist issuer và công suất CP đặt khi deploy, không đổi được (SPEC mục 3).
contract DeviceRegistry {
    uint64 public constant GROUP_MAX_CAPACITY_W = 5_000_000; // Production Group ≤ 5 MW (§7.7)
    uint16 public constant GROUP_MAX_MEMBERS = 50;
    uint32 public constant OPEN = type(uint32).max; // chưa đóng đăng ký

    struct Device {
        bytes32 cpId;
        uint64 capacityW;
        uint32 effectiveDay; // ngày đăng ký hiệu lực: không phát hành cho kỳ bắt đầu trước ngày này (§8.2)
        uint32 endDay; // ngày đóng đăng ký: không phát hành cho ngày ≥ endDay
        bool isGroup;
        uint16 memberCount;
        bool exists;
    }

    /// Một đoạn quản lý: từ `fromDay`, issuer `issuer` phụ trách thiết bị.
    struct Stewardship {
        uint32 fromDay;
        address issuer;
    }

    mapping(address => bool) public isIssuer;
    mapping(bytes32 => uint64) public cpCapacityW; // công suất AC của CP đã được xác minh khi đăng ký (§7.4, giả định A1)
    mapping(bytes32 => Device) private _devices;
    mapping(bytes32 => Stewardship[]) private _stewards;

    event DeviceRegistered(bytes32 indexed deviceId, bytes32 indexed cpId, address indexed issuer, uint64 capacityW,
        uint32 effectiveDay, bool isGroup);
    event RegistrationTransferred(bytes32 indexed deviceId, address indexed from, address indexed to, uint32 effectiveDay);
    event RegistrationClosed(bytes32 indexed deviceId, uint32 endDay);

    error NotIssuer();
    error UnknownCP(bytes32 cpId);
    error DuplicateDevice(bytes32 deviceId);
    error UnknownDevice(bytes32 deviceId);
    error InvalidGroup();
    error InvalidCapacity();
    error NotCurrentIssuer();
    error InvalidDay();

    constructor(address[] memory issuers, bytes32[] memory cpIds, uint64[] memory cpCapacities) {
        require(cpIds.length == cpCapacities.length, "cp length");
        for (uint256 i = 0; i < issuers.length; i++) isIssuer[issuers[i]] = true;
        for (uint256 i = 0; i < cpIds.length; i++) cpCapacityW[cpIds[i]] = cpCapacities[i];
    }

    modifier onlyIssuer() {
        if (!isIssuer[msg.sender]) revert NotIssuer();
        _;
    }

    function registerDevice(bytes32 deviceId, bytes32 cpId, uint64 capacityW, uint32 effectiveDay, bool isGroup,
        uint16 memberCount) external onlyIssuer {
        if (_devices[deviceId].exists) revert DuplicateDevice(deviceId);
        uint64 cpCap = cpCapacityW[cpId];
        if (cpCap == 0) revert UnknownCP(cpId);
        if (capacityW == 0 || capacityW > cpCap) revert InvalidCapacity();
        if (isGroup && (capacityW > GROUP_MAX_CAPACITY_W || memberCount == 0 || memberCount > GROUP_MAX_MEMBERS)) {
            revert InvalidGroup();
        }
        _devices[deviceId] = Device(cpId, capacityW, effectiveDay, OPEN, isGroup, isGroup ? memberCount : 1, true);
        _stewards[deviceId].push(Stewardship(effectiveDay, msg.sender));
        emit DeviceRegistered(deviceId, cpId, msg.sender, capacityW, effectiveDay, isGroup);
    }

    /// @notice Chuyển thiết bị sang issuer khác từ `effectiveDay`, giữ nguyên mã và lịch sử (§16.3).
    function transferRegistration(bytes32 deviceId, address newIssuer, uint32 effectiveDay) external {
        Device storage d = _requireDevice(deviceId);
        Stewardship[] storage s = _stewards[deviceId];
        Stewardship storage last = s[s.length - 1];
        if (msg.sender != last.issuer) revert NotCurrentIssuer();
        if (!isIssuer[newIssuer] || newIssuer == msg.sender) revert NotIssuer();
        if (effectiveDay <= last.fromDay || effectiveDay >= d.endDay) revert InvalidDay();
        s.push(Stewardship(effectiveDay, newIssuer));
        emit RegistrationTransferred(deviceId, msg.sender, newIssuer, effectiveDay);
    }

    /// @notice Đóng đăng ký: không phát hành cho ngày ≥ `endDay` (§8.2).
    function closeRegistration(bytes32 deviceId, uint32 endDay) external {
        Device storage d = _requireDevice(deviceId);
        Stewardship[] storage s = _stewards[deviceId];
        if (msg.sender != s[s.length - 1].issuer) revert NotCurrentIssuer();
        if (endDay < d.effectiveDay || d.endDay != OPEN) revert InvalidDay();
        d.endDay = endDay;
        emit RegistrationClosed(deviceId, endDay);
    }

    function deviceOf(bytes32 deviceId) external view returns (bytes32 cpId, address issuer, uint64 capacityW,
        uint32 effectiveDay, uint32 endDay, bool isGroup) {
        Device storage d = _requireDevice(deviceId);
        Stewardship[] storage s = _stewards[deviceId];
        return (d.cpId, s[s.length - 1].issuer, d.capacityW, d.effectiveDay, d.endDay, d.isGroup);
    }

    function exists(bytes32 deviceId) external view returns (bool) {
        return _devices[deviceId].exists;
    }

    /// @notice Issuer phụ trách thiết bị ở ngày `day` (address(0) nếu trước ngày đăng ký hiệu lực).
    function issuerOn(bytes32 deviceId, uint32 day) public view returns (address issuer) {
        Stewardship[] storage s = _stewards[deviceId];
        for (uint256 i = 0; i < s.length; i++) {
            if (day >= s[i].fromDay) issuer = s[i].issuer;
        }
    }

    function _requireDevice(bytes32 deviceId) private view returns (Device storage d) {
        d = _devices[deviceId];
        if (!d.exists) revert UnknownDevice(deviceId);
    }
}
