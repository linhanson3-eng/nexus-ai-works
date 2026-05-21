"""Workshop Bridge — inter-workshop data sharing.

Enables workshops to share products and memories with each other
through the Warehouse (file-based) and Global Memory Tree (SQLite).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class WorkshopBridge:
    """Bridge for inter-workshop communication.

    Workshops are isolated by design. The bridge provides controlled
    read access to peer workshop outputs and shared memories.
    """

    def __init__(self, warehouse: Any, memory_store: Any = None):
        self.warehouse = warehouse
        self.memory_store = memory_store

    def share_product(
        self,
        from_workshop: str,
        filename: str,
        to_workshop: str,
        to_filename: str = "",
    ) -> str:
        """Share a workshop product with another workshop via symbolic link.

        Args:
            from_workshop: Source workshop name.
            filename: Product filename in the source workshop.
            to_workshop: Target workshop name.
            to_filename: Destination filename (defaults to same as source).

        Returns:
            The markdown link string.
        """
        to_file = to_filename or filename
        link = self.warehouse.link(from_workshop, filename, to_workshop, to_file)
        return link

    def read_peer_product(self, peer_workshop: str, filename: str) -> str:
        """Read a product from another workshop (read-only).

        Args:
            peer_workshop: Name of the peer workshop.
            filename: Product filename to read.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If the product does not exist.
        """
        return self.warehouse.read(peer_workshop, filename)

    def list_peer_products(self, peer_workshop: str) -> list[str]:
        """List all products in a peer workshop.

        Args:
            peer_workshop: Name of the peer workshop.

        Returns:
            List of product filenames.
        """
        paths = self.warehouse.read_dept(peer_workshop)
        return [p.name for p in paths]

    def share_memory(
        self,
        from_tree_id: str,
        content: str,
        to_tree_id: str,
    ) -> None:
        """Write a memory chunk visible to another workshop's tree.

        Args:
            from_tree_id: Source tree ID.
            content: Memory content to share.
            to_tree_id: Target tree ID.
        """
        if self.memory_store is None:
            return
        # Placeholder for cross-tree memory writes.
        # Extended in future iterations when the memory layer
        # supports first-class cross-tree sharing primitives.
        pass

    def list_all_departments(self) -> dict[str, list[str]]:
        """List all workshops and their products.

        Returns:
            Dictionary mapping department names to lists of product filenames.
        """
        return self.warehouse.index()
