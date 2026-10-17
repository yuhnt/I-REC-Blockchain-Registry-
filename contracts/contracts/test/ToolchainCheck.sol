// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";

/// @notice Contract tạm để kiểm tra toolchain (solc + OpenZeppelin).
/// Xóa cùng test/toolchain.ts khi có contract thật ở giai đoạn 3.
contract ToolchainCheck is ERC1155 {
    constructor() ERC1155("") {}

    function mint(address to, uint256 id, uint256 amountWh) external {
        _mint(to, id, amountWh, "");
    }
}
