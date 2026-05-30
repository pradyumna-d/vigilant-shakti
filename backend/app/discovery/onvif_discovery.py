import asyncio
import logging
import socket
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

WS_DISCOVERY_ADDR = ("239.255.255.250", 3702)
PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <e:Header>
  <w:MessageID>uuid:{message_id}</w:MessageID>
  <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
  <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
 </e:Header>
 <e:Body>
  <d:Probe>
   <d:Types>dn:NetworkVideoTransmitter</d:Types>
  </d:Probe>
 </e:Body>
</e:Envelope>"""


@dataclass
class DiscoveredCamera:
    ip_address: str
    onvif_endpoint: str
    manufacturer: str | None = None
    model: str | None = None


def _extract_xaddr(response: str) -> str | None:
    start = response.find("<d:XAddrs>")
    end = response.find("</d:XAddrs>")
    if start == -1 or end == -1:
        start = response.find("<XAddrs>")
        end = response.find("</XAddrs>")
        if start == -1 or end == -1:
            return None
        return response[start + len("<XAddrs>") : end].strip().split()[0]
    return response[start + len("<d:XAddrs>") : end].strip().split()[0]


def _scan(timeout_seconds: float = 3.0) -> list[DiscoveredCamera]:
    results: dict[str, DiscoveredCamera] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout_seconds)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    try:
        payload = PROBE.format(message_id=uuid.uuid4()).encode()
        sock.sendto(payload, WS_DISCOVERY_ADDR)
        while True:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                break
            text = data.decode(errors="ignore")
            endpoint = _extract_xaddr(text)
            if not endpoint:
                continue
            parsed = urlparse(endpoint)
            ip = parsed.hostname or addr[0]
            results[endpoint] = DiscoveredCamera(ip_address=ip, onvif_endpoint=endpoint)
    finally:
        sock.close()
    logger.info("onvif_discovery_complete count=%s", len(results))
    return list(results.values())


async def scan_onvif(timeout_seconds: float = 3.0) -> list[DiscoveredCamera]:
    return await asyncio.to_thread(_scan, timeout_seconds)
