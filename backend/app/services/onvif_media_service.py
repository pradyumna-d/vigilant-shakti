import asyncio
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse

import httpx

logger = logging.getLogger(__name__)

SOAP_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
  xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
  xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
  xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    {body}
  </s:Body>
</s:Envelope>
"""


def _build_rtsp_url(rtsp_url: str, username: str, password: str) -> str:
    parsed = urlparse(rtsp_url)
    if parsed.scheme != "rtsp" or not parsed.hostname:
        return rtsp_url
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return parsed._replace(netloc=f"{auth}{host}").geturl()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(payload: str) -> ET.Element:
    return ET.fromstring(payload.encode("utf-8"))


def _first_text(root: ET.Element, local_name: str) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) == local_name and element.text:
            return element.text.strip()
    return None


def _first_profile_token(root: ET.Element) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) != "Profiles":
            continue
        token = element.attrib.get("token")
        if token:
            return token
    return None


def _soap_post(client: httpx.Client, endpoint: str, action: str, body: str) -> ET.Element:
    response = client.post(
        endpoint,
        content=SOAP_ENVELOPE.format(body=body),
        headers={
            "Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"',
        },
    )
    response.raise_for_status()
    return _parse_xml(response.text)


def _resolve_rtsp_url(onvif_endpoint: str, username: str, password: str) -> str:
    with httpx.Client(auth=httpx.DigestAuth(username, password), timeout=10) as client:
        capabilities = _soap_post(
            client,
            onvif_endpoint,
            "http://www.onvif.org/ver10/device/wsdl/GetCapabilities",
            """
            <tds:GetCapabilities>
              <tds:Category>Media</tds:Category>
            </tds:GetCapabilities>
            """,
        )
        media_xaddr = _first_text(capabilities, "XAddr")
        if not media_xaddr:
            raise RuntimeError("Camera did not return an ONVIF media endpoint")

        profiles = _soap_post(
            client,
            media_xaddr,
            "http://www.onvif.org/ver10/media/wsdl/GetProfiles",
            "<trt:GetProfiles />",
        )
        profile_token = _first_profile_token(profiles)
        if not profile_token:
            raise RuntimeError("Camera returned no ONVIF media profiles")

        stream_uri = _soap_post(
            client,
            media_xaddr,
            "http://www.onvif.org/ver10/media/wsdl/GetStreamUri",
            f"""
            <trt:GetStreamUri>
              <trt:StreamSetup>
                <tt:Stream>RTP-Unicast</tt:Stream>
                <tt:Transport>
                  <tt:Protocol>RTSP</tt:Protocol>
                </tt:Transport>
              </trt:StreamSetup>
              <trt:ProfileToken>{profile_token}</trt:ProfileToken>
            </trt:GetStreamUri>
            """,
        )
    uri = _first_text(stream_uri, "Uri")
    if not uri:
        raise RuntimeError("Camera did not return an RTSP stream URI")
    logger.info(
        "onvif_rtsp_resolved endpoint=%s profile=%s media_endpoint=%s",
        onvif_endpoint,
        profile_token,
        media_xaddr,
    )
    return _build_rtsp_url(uri, username, password)


async def resolve_rtsp_url(onvif_endpoint: str, username: str, password: str) -> str:
    return await asyncio.to_thread(_resolve_rtsp_url, onvif_endpoint, username, password)
