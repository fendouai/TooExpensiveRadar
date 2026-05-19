from __future__ import annotations

import os
from typing import Any

import httpx


class GumroadPublisher:
    BASE_URL = "https://api.gumroad.com/v2"

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or os.getenv("GUMROAD_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("GUMROAD_ACCESS_TOKEN is not set")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def list_products(self) -> list[dict[str, Any]]:
        resp = httpx.get(f"{self.BASE_URL}/products", headers=self._headers())
        resp.raise_for_status()
        return resp.json().get("products", [])

    def create_product(
        self,
        name: str,
        price: int,
        description: str = "",
        url: str = "",
        tags: list[str] | None = None,
        published: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "product": {
                "name": name,
                "price": price,
                "description": description,
                "url": url,
                "published": published,
            }
        }
        if tags:
            payload["product"]["tags"] = ",".join(tags)

        resp = httpx.post(
            f"{self.BASE_URL}/products",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def disable_product(self, product_id: str) -> dict[str, Any]:
        resp = httpx.post(
            f"{self.BASE_URL}/products/{product_id}/disable",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_product(self, product_id: str) -> dict[str, Any]:
        resp = httpx.get(
            f"{self.BASE_URL}/products/{product_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()


class LemonsqueezyPublisher:
    BASE_URL = "https://api.lemonsqueezy.com/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("LEMONSQUEEZY_API_KEY")
        if not self.api_key:
            raise ValueError("LEMONSQUEEZY_API_KEY is not set")
        self.store_id = os.getenv("LEMONSQUEEZY_STORE_ID")
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
            },
            timeout=30.0,
        )

    def _mk(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = self._client.request(method, f"{self.BASE_URL}{path}", **kwargs)
        resp.raise_for_status()
        return resp

    def list_products(self) -> list[dict[str, Any]]:
        resp = self._mk("GET", "/products")
        data = resp.json()
        return data.get("data", [])

    def upload_file(self, file_bytes: bytes, filename: str) -> str:
        import base64, uuid

        b64 = base64.b64encode(file_bytes).decode()
        boundary = uuid.uuid4().hex

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

        resp = self._client.post(
            f"{self.BASE_URL}/files",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/vnd.api+json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            content=body,
        )
        resp.raise_for_status()
        files = resp.json().get("data", [])
        if files:
            return files[0]["attributes"]["download_url"]
        raise ValueError("No file returned from upload")

    def create_product(
        self,
        name: str,
        price: int,
        description: str = "",
        file_url: str = "",
        store_id: int | None = None,
    ) -> dict[str, Any]:
        sid = store_id or int(self.store_id or 0)

        product_payload = {
            "data": {
                "type": "products",
                "attributes": {
                    "name": name,
                    "slug": f"{name.lower().replace(' ', '-')}-{id(self)}",
                    "description": description,
                    "status": "published",
                },
                "relationships": {
                    "store": {"data": {"type": "stores", "id": str(sid)}}
                },
            }
        }
        resp = self._mk("POST", "/products", json=product_payload)
        product_data = resp.json()["data"]
        product_id = product_data["id"]

        variant_payload = {
            "data": {
                "type": "variants",
                "attributes": {
                    "name": "Default",
                    "price": price,
                },
                "relationships": {
                    "product": {"data": {"type": "products", "id": product_id}}
                },
            }
        }
        variant_resp = self._mk("POST", "/variants", json=variant_payload)
        variant_data = variant_resp.json()["data"]
        variant_id = variant_data["id"]

        if file_url:
            file_payload = {
                "data": {
                    "type": "files",
                    "attributes": {"name": filename, "url": file_url},
                    "relationships": {
                        "variant": {"data": {"type": "variants", "id": variant_id}}
                    },
                }
            }
            self._mk("POST", "/files", json=file_payload)

        return {"product": product_data, "variant": variant_data}

    def get_checkout_url(self, variant_id: str) -> str:
        return f"https://{self.store_id}.lemonsqueezy.com/checkout/buy/{variant_id}"
