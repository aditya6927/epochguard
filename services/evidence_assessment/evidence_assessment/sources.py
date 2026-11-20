from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import ipaddress
import re
from urllib.parse import urlsplit

from publicsuffix2 import PublicSuffixList
from .config import Failure
from .schema import Source

PSL = PublicSuffixList()  # Bundled snapshot only; never fetches network data.
OWNERS = {"apnews.com":"associated-press", "ap.org":"associated-press",
          "reuters.com":"reuters", "thomsonreuters.com":"reuters", "bbc.com":"bbc", "bbc.co.uk":"bbc"}


def publisher(url):
    if not isinstance(url, str) or len(url)>2048 or any(ord(c)<33 or ord(c)>126 for c in url) or "\\" in url:
        raise ValueError("invalid source url")
    parts=urlsplit(url)
    host=parts.hostname
    if parts.scheme!="https" or not host or parts.username is not None or parts.password is not None or parts.port not in (None,443):
        raise ValueError("invalid source authority")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?",host) or ".." in host:
        raise ValueError("invalid source host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP source links refused")
    domain=PSL.get_sld(host,strict=True)
    if not domain or domain==PSL.get_tld(host,strict=True) or host.endswith((".local",".internal",".test",".invalid")):
        raise ValueError("unrecognized source domain")
    for suffix,key in ((".go.jp","government-japan"),(".gov.uk","government-uk"),
                       (".gov.au","government-australia"),(".gov","government-us"),(".mil","government-us")):
        if host.endswith(suffix): return key
    return OWNERS.get(domain,domain)


def publication(value):
    if value is None: return None
    if not isinstance(value,str) or len(value)>80: raise ValueError("invalid publication metadata")
    try:
        result=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        result=parsedate_to_datetime(value)
    if result.tzinfo is None: result=result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def validated_results(value, retrieved_at):
    try:
        rows=value["results"]
        if not isinstance(rows,list) or len(rows)>5: raise ValueError()
        sources=[]
        urls=set()
        for i,row in enumerate(rows,1):
            if not isinstance(row,dict) or row.get("raw_content") not in (None,""):
                raise ValueError()
            group=publisher(row["url"])
            if row["url"] in urls: raise ValueError()
            urls.add(row["url"])
            score=row.get("score")
            if score is not None and (type(score) not in (int,float) or not 0<=score<=1): raise ValueError()
            published=publication(row.get("published_date"))
            if published is not None and published>retrieved_at: raise ValueError()
            sources.append(Source(id=f"S{i}",url=row["url"],title=row["title"],snippet=row["content"],
                publisher_group=group,retrieved_at=retrieved_at,published_at=published,
                publication_basis="unknown" if published is None else "provider_metadata_unverified"))
        return sources
    except Exception:
        raise Failure("INVALID_SEARCH_EVIDENCE") from None
