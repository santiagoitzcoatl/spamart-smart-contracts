import smartpy as sp


class DAOTokenDrop(sp.Contract):
    """This contract implements DAO token drop distribution using a Merkle tree.

    The code is highly based on the Token Drop template by Anshu Jalan:
    https://github.com/AnshuJalan/token-drop-template

    """

    FA2_TXS_TYPE = sp.TList(sp.TRecord(
        to_=sp.TAddress,
        token_id=sp.TNat,
        amount=sp.TNat).layout(
            ("to_", ("token_id", "amount"))))

    def __init__(self, administrator, metadata, token, token_to_swap, merkle_root):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrador
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The DAO token address
            token=sp.TAddress,
            # The address of the token to swap
            token_to_swap=sp.TAddress,
            # The Merkle tree root associated to DAO the distribution list
            merkle_root=sp.TBytes,
            # The big map with the users that already claimed their tokens
            claimed=sp.TBigMap(sp.TAddress, sp.TNat),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            token=token,
            token_to_swap=token_to_swap,
            merkle_root=merkle_root,
            claimed=sp.big_map(),
            proposed_administrator=sp.none)

    def verify_proof(self, proof, leaf):
        """Computes the Merkle tree root from the provided proof and leaf and
        checks that it coincides with the stored merkle root.

        """
        # Loop over the proof elements and calculate the combined hash
        combined_hash = sp.local("combined_hash", sp.sha256(leaf))

        with sp.for_("proof_element", proof) as proof_element:
            with sp.if_(combined_hash.value < proof_element):
                combined_hash.value = sp.sha256(combined_hash.value + proof_element)
            with sp.else_():
                combined_hash.value = sp.sha256(proof_element + combined_hash.value)

        # Check that the combined hash coincides with the stored Merkle root
        sp.verify(combined_hash.value == self.data.merkle_root,
                  message="DROP_INVALID_MERKLE_PROOF")

    @sp.entry_point
    def claim(self, params):
        """Claims some DAO tokens.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proof=sp.TList(sp.TBytes),
            leaf=sp.TBytes).layout(("proof", "leaf")))

        # Unpack the leaf data
        leaf_data_type = sp.TRecord(
            address=sp.TAddress,
            value=sp.TNat).layout(("address", "value"))
        leaf_data = sp.compute(sp.unpack(
            params.leaf, leaf_data_type).open_some("DROP_INVALID_LEAF"))

        # Check that the sender coincides with the leaf address
        sp.verify(sp.sender == leaf_data.address,
                  message="DROP_SENDER_NOT_LEAF")

        # Check that the sender didn't claim all the tokens
        unclaimed_tokens = sp.compute(sp.as_nat(
            leaf_data.value - self.data.claimed.get(sp.sender, 0)))
        sp.verify(unclaimed_tokens > 0, message="DROP_ALL_TOKENS_CLAIMED")

        # Check that the provided proof is correct
        self.verify_proof(params.proof, params.leaf)

        # Get a handle to the DAO token transfer entry point
        token_transfer_handle = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=DAOTokenDrop.FA2_TXS_TYPE)),
            address=self.data.token,
            entry_point="transfer").open_some()

        # Transfer the remaining DAO token editions to the sender
        sp.transfer(
            arg=sp.list([sp.record(
                from_=sp.self_address,
                txs=sp.list([sp.record(
                    to_=sp.sender,
                    token_id=sp.nat(0),
                    amount=unclaimed_tokens)]))]),
            amount=sp.mutez(0),
            destination=token_transfer_handle)

        # Update the claimed big map
        self.data.claimed[sp.sender] = leaf_data.value

    @sp.entry_point
    def transfer(self, params):
        """Transfers some DAO tokens to a list of addresses.

        """
        # Define the input parameter data type
        sp.set_type(params, DAOTokenDrop.FA2_TXS_TYPE)

        # Check that the administrator executed the entry point
        sp.verify(sp.sender == self.data.administrator,
                  message="DROP_NOT_ADMIN")

        # Get a handle to the DAO token transfer entry point
        token_transfer_handle = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=DAOTokenDrop.FA2_TXS_TYPE)),
            address=self.data.token,
            entry_point="transfer").open_some()

        # Execute the tranfer
        sp.transfer(
            arg=sp.list([sp.record(
                from_=sp.self_address,
                txs=params)]),
            amount=sp.mutez(0),
            destination=token_transfer_handle)


sp.add_compilation_target("daoTokenDrop", DAOTokenDrop(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    token=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekaa"),
    token_to_swap=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekbb"),
    merkle_root=sp.bytes("0x00")))
