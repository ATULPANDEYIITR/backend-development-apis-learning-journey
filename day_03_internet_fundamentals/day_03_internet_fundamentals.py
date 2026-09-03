"""
===============================================================================
INTERNET FUNDAMENTALS
===============================================================================

Topic:
Internet, ISP, Packets, Routing, IP Addresses, Ports, Sockets,
TCP/IP Basics, Terminal, ping, tracert/traceroute

Purpose:
This is a comprehensive beginner-to-advanced educational Python script.

The script explains:
    1. What the Internet is
    2. Internet vs World Wide Web
    3. Clients and servers
    4. ISPs
    5. Networks and network devices
    6. Packets
    7. IP addresses
    8. IPv4 and IPv6
    9. Public and private IP addresses
   10. MAC addresses
   11. Subnets and CIDR
   12. Default gateway
   13. DNS
   14. DHCP
   15. Routing
   16. Routers and routing tables
   17. Ports
   18. Sockets
   19. TCP
   20. UDP
   21. TCP/IP model
   22. OSI model
   23. Encapsulation and decapsulation
   24. ARP
   25. ICMP
   26. ping
   27. tracert / traceroute
   28. HTTP and HTTPS
   29. TLS basics
   30. Firewalls
   31. NAT
   32. Proxies
   33. VPN basics
   34. Network troubleshooting
   35. Python socket programming
   36. TCP client/server programming
   37. UDP programming
   38. DNS lookup with Python
   39. Practical network inspection
   40. Advanced concepts
   41. Practical exercises
   42. Final learning summary

Requirements:
    Python 3.x

Most examples use only Python's standard library.

IMPORTANT:
Some commands demonstrated in this file must be executed from a real
terminal/command prompt rather than inside Python.

===============================================================================
"""


# =============================================================================
# SECTION 1 - BASIC PYTHON IMPORTS
# =============================================================================

import socket
import struct
import subprocess
import platform
import ipaddress
import sys
import time


# =============================================================================
# SECTION 2 - HELPER FUNCTIONS
# =============================================================================

def title(text):
    """Print a major section heading."""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)


def subtitle(text):
    """Print a subsection heading."""
    print("\n" + "-" * 80)
    print(text)
    print("-" * 80)


def explain(term, explanation):
    """Print a concept and its explanation."""
    print(f"\n{term}")
    print(explanation)


def run_command(command):
    """
    Run a terminal command safely and display its output.

    This function is intentionally simple for educational purposes.
    """
    print(f"\nRunning command: {command}")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        return result.returncode

    except subprocess.TimeoutExpired:
        print("Command timed out.")

    except Exception as error:
        print(f"Error: {error}")

    return None


# =============================================================================
# SECTION 3 - WHAT IS THE INTERNET?
# =============================================================================

title("1. WHAT IS THE INTERNET?")

explain(
    "Internet",
    """
The Internet is a global system of interconnected computer networks.

It allows computers, phones, servers, cloud systems, routers, IoT devices,
and other networked systems to communicate using standardized protocols.

The Internet is NOT one giant computer.

It is a network of networks.

A simplified representation is:

    Your Computer
          |
       Router
          |
        ISP
          |
    Internet Backbone
          |
    Multiple Routers
          |
     Destination ISP
          |
    Destination Server


Important idea:

The Internet works because independent networks agree to communicate using
common protocols such as:

    IP
    TCP
    UDP
    ICMP
    DNS
    HTTP
    HTTPS
    TLS
    DHCP
    ARP


The Internet is decentralized.

There is no single machine that forwards every Internet packet.
"""
)


# =============================================================================
# SECTION 4 - INTERNET VS WORLD WIDE WEB
# =============================================================================

title("2. INTERNET VS WORLD WIDE WEB")

explain(
    "Internet",
    """
The Internet is the underlying global networking infrastructure.

It includes:

    Routers
    Fiber-optic cables
    Cellular networks
    Wi-Fi networks
    Data centers
    ISPs
    DNS infrastructure
    Network protocols
    Servers
    Network devices
"""
)

explain(
    "World Wide Web",
    """
The Web is a service that runs on top of the Internet.

Websites and web applications use protocols such as HTTP and HTTPS.

For example:

    Browser
       |
      HTTPS
       |
    Internet
       |
    Web Server

Therefore:

    Internet != Web

The Web is one of many services that use the Internet.

Other Internet services include:

    Email
    SSH
    DNS
    FTP
    Online gaming
    Video conferencing
    VoIP
    Cloud APIs
"""


# =============================================================================
# SECTION 5 - CLIENT AND SERVER
# =============================================================================

title("3. CLIENTS AND SERVERS")

explain(
    "Client",
    """
A client is a system that initiates communication or requests a service.

Examples:

    Web browser
    Mobile application
    Python program
    Email application
    SSH client
"""
)

explain(
    "Server",
    """
A server provides a service to clients.

Examples:

    Web server
    Database server
    DNS server
    Mail server
    File server
    API server
"""
)

print("""
Example:

    Browser
       |
       | HTTPS request
       v
    Web Server
       |
       | HTTP response
       v
    Browser

The server normally listens for incoming connections on a particular port.
""")


# =============================================================================
# SECTION 6 - ISP
# =============================================================================

title("4. WHAT IS AN ISP?")

explain(
    "ISP - Internet Service Provider",
    """
An ISP provides connectivity between your local network and larger networks,
ultimately providing access to the Internet.

Examples of ISP functions include:

    Internet connectivity
    IP address assignment
    DNS services
    Network routing
    Customer authentication
    Broadband access
    Fiber connectivity
    Mobile connectivity

Typical structure:

    Laptop
       |
    Home Router
       |
    ISP Access Network
       |
    ISP Core
       |
    Internet
"""
)

print("""
Common types of Internet access:

    Fiber
    DSL
    Cable
    Mobile/Cellular
    Satellite
    Fixed wireless

Your ISP may assign your router a public IPv4 address, an IPv6 address,
or both.
""")


# =============================================================================
# SECTION 7 - NETWORKS
# =============================================================================

title("5. WHAT IS A COMPUTER NETWORK?")

explain(
    "Network",
    """
A network is a collection of devices connected so they can exchange data.

Devices may include:

    Computers
    Phones
    Servers
    Routers
    Switches
    Printers
    Cameras
    IoT devices
"""
)

print("""
Common network categories:

LAN
    Local Area Network

WAN
    Wide Area Network

MAN
    Metropolitan Area Network

WLAN
    Wireless Local Area Network

Internet
    Global interconnection of many networks
""")


# =============================================================================
# SECTION 8 - NETWORK DEVICES
# =============================================================================

title("6. IMPORTANT NETWORK DEVICES")

explain(
    "Switch",
    """
A switch primarily connects devices within a local network.

It operates mainly at Layer 2 of the OSI model.

It uses MAC addresses to forward Ethernet frames.
"""
)

explain(
    "Router",
    """
A router connects different IP networks.

It uses IP addresses and routing information to decide where packets should
go next.

Example:

    192.168.1.0/24
          |
       Router
          |
    10.0.0.0/24
"""
)

explain(
    "Access Point",
    """
A wireless access point allows wireless devices to connect to a network.
"""
)

explain(
    "Firewall",
    """
A firewall controls network traffic according to security rules.

It may filter traffic based on:

    Source IP
    Destination IP
    Source port
    Destination port
    Protocol
    Connection state
    Application characteristics
"""
)


# =============================================================================
# SECTION 9 - PACKETS
# =============================================================================

title("7. WHAT IS A PACKET?")

explain(
    "Packet",
    """
A packet is a formatted unit of network-layer data.

When a large piece of information is transmitted over a network, it is
typically divided into smaller units.

For example:

    Large Data
        |
        v
    +---------+
    | Packet 1|
    +---------+
    | Packet 2|
    +---------+
    | Packet 3|
    +---------+
    | Packet 4|
    +---------+

The packets can travel through network infrastructure.

At the destination, the data is processed and reconstructed according to
the protocol being used.
"""
)

print("""
A simplified packet concept:

    +-------------------------------+
    | IP Header                     |
    +-------------------------------+
    | TCP/UDP Header                |
    +-------------------------------+
    | Application Data              |
    +-------------------------------+

Real packets can contain many additional fields.
""")


# =============================================================================
# SECTION 10 - PACKET SWITCHING
# =============================================================================

title("8. PACKET SWITCHING")

explain(
    "Packet Switching",
    """
Packet switching means data is transmitted as separate packets.

Each packet contains addressing and control information.

Network devices examine relevant headers and forward traffic toward its
destination.

This is fundamentally different from a dedicated physical circuit for
every communication session.

The Internet is primarily based on packet-switched networking.
"""
)


# =============================================================================
# SECTION 11 - IP ADDRESSES
# =============================================================================

title("9. IP ADDRESSES")

explain(
    "IP Address",
    """
An IP address identifies a network interface at the Internet Protocol layer.

It allows network traffic to identify a source and destination.

Example IPv4 address:

    192.168.1.10

Example IPv6 address:

    2001:db8::10
"""
)


# =============================================================================
# SECTION 12 - IPv4
# =============================================================================

title("10. IPv4")

explain(
    "IPv4",
    """
IPv4 uses 32-bit addresses.

A typical IPv4 address is represented using four decimal octets.

Example:

    192.168.1.10

Binary representation:

    11000000.10101000.00000001.00001010

Each octet is 8 bits.

Therefore:

    8 + 8 + 8 + 8 = 32 bits
"""
)


# =============================================================================
# SECTION 13 - IPv6
# =============================================================================

title("11. IPv6")

explain(
    "IPv6",
    """
IPv6 uses 128-bit addresses.

Example:

    2001:db8:abcd:0012:0000:0000:0000:0001

IPv6 was developed partly because the available IPv4 address space is
limited.

IPv6 provides an enormous address space.

IPv6 also includes features such as:

    Global addressing
    Stateless address configuration
    Neighbor Discovery
    Multicast
    Improved address scalability
"""
)


# =============================================================================
# SECTION 14 - PRIVATE IP ADDRESSES
# =============================================================================

title("12. PRIVATE AND PUBLIC IP ADDRESSES")

explain(
    "Private IPv4 addresses",
    """
Common private IPv4 ranges are:

    10.0.0.0/8

    172.16.0.0/12

    192.168.0.0/16

These addresses are intended for private networks.

Example:

    Laptop: 192.168.1.20
    Phone:  192.168.1.21
    Router: 192.168.1.1
"""
)

explain(
    "Public IP address",
    """
A public IP address is globally routable under normal Internet routing
conditions.

Your router may use a public IP address on its Internet-facing interface.
"""
)


# =============================================================================
# SECTION 15 - LOOPBACK
# =============================================================================

title("13. LOOPBACK ADDRESS")

explain(
    "Loopback",
    """
The IPv4 loopback network is:

    127.0.0.0/8

The most common loopback address is:

    127.0.0.1

The hostname:

    localhost

usually resolves to a loopback address.

Loopback means:

    This computer communicating with itself.

Example:

    Browser
       |
    127.0.0.1
       |
    Local Server
"""
)


# =============================================================================
# SECTION 16 - MAC ADDRESS
# =============================================================================

title("14. MAC ADDRESS")

explain(
    "MAC Address",
    """
A MAC address identifies a network interface at the data-link layer.

Example:

    00:1A:2B:3C:4D:5E

MAC addresses are associated with Ethernet and Wi-Fi networking.

Important distinction:

    MAC address -> local/data-link addressing

    IP address  -> network-layer addressing

A router does not normally route packets across the Internet based on
the destination MAC address.

MAC addresses are relevant within local network segments.
"""
)


# =============================================================================
# SECTION 17 - SUBNET MASK
# =============================================================================

title("15. SUBNET MASK")

explain(
    "Subnet mask",
    """
A subnet mask determines which portion of an IPv4 address represents the
network and which portion represents hosts.

Example:

    IP:
        192.168.1.25

    Mask:
        255.255.255.0

This corresponds to:

    192.168.1.0/24

The /24 means 24 bits are used for the network prefix.
"""
)


# =============================================================================
# SECTION 18 - CIDR
# =============================================================================

title("16. CIDR")

explain(
    "CIDR - Classless Inter-Domain Routing",
    """
CIDR represents an IP network using a prefix length.

Example:

    192.168.1.0/24

The /24 means:

    First 24 bits = network prefix
    Remaining 8 bits = host portion

Number of IPv4 addresses:

    2^(32 - 24)
    = 2^8
    = 256
"""
)

print("""
Other examples:

    10.0.0.0/8
    172.16.0.0/12
    192.168.1.0/24
    192.168.1.0/25
    192.168.1.0/26
""")


# =============================================================================
# SECTION 19 - PYTHON IP ADDRESS CALCULATIONS
# =============================================================================

title("17. PYTHON IP ADDRESS MODULE")

network = ipaddress.ip_network("192.168.1.0/24")
host = ipaddress.ip_address("192.168.1.25")

print("Network:", network)
print("Network address:", network.network_address)
print("Broadcast address:", network.broadcast_address)
print("Prefix length:", network.prefixlen)
print("Number of addresses:", network.num_addresses)
print("Host belongs to network:", host in network)

print("\nFirst five usable-looking addresses:")
for address in list(network.hosts())[:5]:
    print(address)


# =============================================================================
# SECTION 20 - DEFAULT GATEWAY
# =============================================================================

title("18. DEFAULT GATEWAY")

explain(
    "Default gateway",
    """
The default gateway is normally the router a host uses when the destination
is outside the host's directly connected network.

Example:

    Laptop:
        192.168.1.20

    Network:
        192.168.1.0/24

    Gateway:
        192.168.1.1

If the laptop wants to communicate with:

    8.8.8.8

it usually sends the traffic to its default gateway.

Simplified:

    Laptop
      |
      | 192.168.1.1
      v
    Router
      |
    Internet
"""
)


# =============================================================================
# SECTION 21 - DNS
# =============================================================================

title("19. DNS")

explain(
    "DNS - Domain Name System",
    """
DNS translates domain names into IP addresses and supports other types of
name-related information.

Humans prefer:

    example.com

Networks ultimately communicate using addresses such as:

    93.184.216.x

Conceptually:

    Browser
       |
       | DNS query
       v
    DNS Resolver
       |
       | answer
       v
    IP Address

Then the client can connect to the destination IP.
"""
)

print("""
Common DNS record types:

    A       -> IPv4 address
    AAAA    -> IPv6 address
    CNAME   -> Canonical name
    MX      -> Mail exchange
    NS      -> Name server
    TXT     -> Text information
    PTR     -> Reverse lookup
""")


# =============================================================================
# SECTION 22 - DNS LOOKUP USING PYTHON
# =============================================================================

title("20. DNS LOOKUP WITH PYTHON")

domain = "example.com"

try:
    ip = socket.gethostbyname(domain)
    print(f"{domain} -> {ip}")
except socket.gaierror as error:
    print("DNS lookup failed:", error)


# =============================================================================
# SECTION 23 - DHCP
# =============================================================================

title("21. DHCP")

explain(
    "DHCP - Dynamic Host Configuration Protocol",
    """
DHCP can automatically provide network configuration to clients.

A DHCP server may provide:

    IP address
    Subnet mask
    Default gateway
    DNS server
    Lease duration

A simplified DHCP process is commonly remembered as:

    DORA

    Discover
    Offer
    Request
    Acknowledgement
"""
)


# =============================================================================
# SECTION 24 - ROUTING
# =============================================================================

title("22. ROUTING")

explain(
    "Routing",
    """
Routing is the process of determining where network traffic should be
forwarded.

Routers examine destination IP addresses and consult routing information.

Example:

    Destination:
        8.8.8.8

Router asks:

    Which route matches 8.8.8.8?

Then:

    Select best matching route
            |
            v
       Forward packet
"""
)

print("""
Simplified routing table:

    Destination       Next Hop        Interface

    192.168.1.0/24    Direct          eth0
    10.0.0.0/8        192.168.1.1     eth0
    0.0.0.0/0         192.168.1.1     eth0

The 0.0.0.0/0 route is commonly called the default route.
""")


# =============================================================================
# SECTION 25 - LONGEST PREFIX MATCH
# =============================================================================

title("23. LONGEST PREFIX MATCH")

explain(
    "Longest Prefix Match",
    """
When multiple routes match a destination, routers generally prefer the
route with the longest matching prefix.

Example:

    10.0.0.0/8
    10.20.0.0/16
    10.20.30.0/24

Destination:

    10.20.30.50

All three may match.

The /24 route is more specific, so it is preferred.

This principle is fundamental to IP routing.
"""
)


# =============================================================================
# SECTION 26 - ROUTING PROTOCOLS
# =============================================================================

title("24. ROUTING PROTOCOLS")

explain(
    "Routing protocols",
    """
Routing protocols help routers exchange information about networks.

Examples:

    RIP
    OSPF
    IS-IS
    EIGRP
    BGP

BGP is particularly important because it is used to exchange routing
information between autonomous systems on the global Internet.

An Autonomous System is a collection of networks under a common
administrative and routing policy.
"""
)


# =============================================================================
# SECTION 27 - PORTS
# =============================================================================

title("25. PORTS")

explain(
    "Port",
    """
A port identifies a logical communication endpoint associated with a
transport-layer protocol.

Port numbers range from:

    0 to 65535

Ports allow one machine to run many network services simultaneously.

Example:

    192.168.1.10:22
    192.168.1.10:80
    192.168.1.10:443
"""
)

print("""
Common ports:

    20/21  -> FTP
    22     -> SSH
    23     -> Telnet
    25     -> SMTP
    53     -> DNS
    67/68  -> DHCP
    80     -> HTTP
    110    -> POP3
    143    -> IMAP
    443    -> HTTPS
    3306   -> MySQL
    5432   -> PostgreSQL

Ports are not the same thing as protocols.

For example:

    TCP/443

means TCP transport using destination port 443.

A service can sometimes operate on a different port.
"""


# =============================================================================
# SECTION 28 - SOCKETS
# =============================================================================

title("26. SOCKETS")

explain(
    "Socket",
    """
A socket is a programming interface used by applications to communicate
over networks.

A TCP connection can conceptually be identified by:

    Source IP
    Source Port
    Destination IP
    Destination Port
    Protocol

Example:

    192.168.1.20:51524
            |
            | TCP
            v
    93.184.216.34:443
"""
)


# =============================================================================
# SECTION 29 - TCP
# =============================================================================

title("27. TCP")

explain(
    "TCP - Transmission Control Protocol",
    """
TCP provides reliable, ordered, connection-oriented byte-stream delivery.

Important TCP characteristics:

    Connection-oriented
    Reliable delivery
    Ordered data
    Retransmission
    Flow control
    Congestion control
    Error detection
"""
)

print("""
TCP connection establishment:

    Client                         Server
       |                              |
       | -------- SYN ------------->  |
       | <------- SYN-ACK ----------  |
       | -------- ACK ------------->  |
       |                              |
       |       Connection ready      |

This is commonly called the TCP three-way handshake.
""")


# =============================================================================
# SECTION 30 - TCP SEQUENCE NUMBERS
# =============================================================================

title("28. TCP SEQUENCE NUMBERS")

explain(
    "Sequence numbers",
    """
TCP uses sequence numbers to help track bytes in the data stream.

They support:

    Ordering
    Duplicate detection
    Retransmission
    Reliable delivery

If a segment is lost, TCP can detect that expected data has not arrived
and may retransmit it.
"""
)


# =============================================================================
# SECTION 31 - TCP ACKNOWLEDGEMENTS
# =============================================================================

title("29. TCP ACKNOWLEDGEMENTS")

explain(
    "Acknowledgement",
    """
TCP uses acknowledgements to indicate successfully received data.

Simplified:

    Sender ---> Data ---> Receiver
    Sender <--- ACK ----- Receiver

If expected data is missing, TCP mechanisms can cause retransmission.
"""
)


# =============================================================================
# SECTION 32 - TCP CONNECTION TERMINATION
# =============================================================================

title("30. TCP CONNECTION TERMINATION")

print("""
A simplified TCP termination sequence can involve FIN and ACK messages.

    Client                         Server
       |                              |
       | -------- FIN ------------->  |
       | <--------- ACK ------------  |
       | <--------- FIN ------------  |
       | -------- ACK ------------->  |
       |                              |

Real TCP state transitions are more detailed.
""")


# =============================================================================
# SECTION 33 - UDP
# =============================================================================

title("31. UDP")

explain(
    "UDP - User Datagram Protocol",
    """
UDP is a connectionless transport protocol.

UDP does not provide TCP-style reliable ordered byte-stream delivery.

UDP is often useful when low overhead and application-controlled behavior
are important.

Examples of technologies that may use UDP include:

    DNS
    DHCP
    VoIP
    Streaming
    Online games
    QUIC/HTTP-3 transport

UDP does not automatically mean:

    Fast

or:

    Unreliable application

It simply provides fewer transport-layer guarantees than TCP.
"""
)


# =============================================================================
# SECTION 34 - TCP VS UDP
# =============================================================================

title("32. TCP VS UDP")

print("""
+----------------------+-------------------------+-------------------------+
| Feature              | TCP                     | UDP                     |
+----------------------+-------------------------+-------------------------+
| Connection           | Connection-oriented     | Connectionless          |
| Ordering             | Yes                     | No built-in ordering    |
| Reliability          | Yes                     | No TCP-style reliability|
| Retransmission       | Yes                     | No built-in             |
| Flow control         | Yes                     | No TCP-style mechanism  |
| Congestion control   | Yes                     | Application-dependent   |
| Overhead             | Higher                  | Lower                   |
| Typical use          | Web, SSH, databases     | DNS, games, media       |
+----------------------+-------------------------+-------------------------+
""")


# =============================================================================
# SECTION 35 - TCP/IP MODEL
# =============================================================================

title("33. TCP/IP MODEL")

explain(
    "TCP/IP model",
    """
A practical TCP/IP model can be represented using four layers:

    1. Application
    2. Transport
    3. Internet
    4. Link

Application layer examples:

    HTTP
    HTTPS
    DNS
    SSH
    SMTP

Transport layer:

    TCP
    UDP

Internet layer:

    IP
    ICMP

Link layer:

    Ethernet
    Wi-Fi
    ARP-related local network mechanisms
"""
)


# =============================================================================
# SECTION 36 - OSI MODEL
# =============================================================================

title("34. OSI MODEL")

print("""
OSI has seven conceptual layers:

    7. Application
    6. Presentation
    5. Session
    4. Transport
    3. Network
    2. Data Link
    1. Physical

Useful associations:

    Application -> HTTP, DNS, SSH
    Transport  -> TCP, UDP
    Network    -> IP, ICMP
    Data Link  -> Ethernet, Wi-Fi
    Physical   -> electrical/radio/optical signaling

The OSI model is primarily a conceptual framework.
The TCP/IP model more directly reflects Internet protocol architecture.
""")


# =============================================================================
# SECTION 37 - ENCAPSULATION
# =============================================================================

title("35. ENCAPSULATION")

explain(
    "Encapsulation",
    """
When an application sends data, protocol layers add their own headers.

Simplified:

    Application Data
          |
          v
    TCP Header + Data
          |
          v
    IP Header + TCP Header + Data
          |
          v
    Ethernet Header + IP Header + TCP Header + Data + Trailer

At the destination, the process is reversed.

This is called decapsulation.
"""
)


# =============================================================================
# SECTION 38 - ARP
# =============================================================================

title("36. ARP")

explain(
    "ARP - Address Resolution Protocol",
    """
In traditional IPv4 local networking, ARP helps map an IPv4 address to a
local MAC address.

Example:

    IP:
        192.168.1.1

Question:

    Which MAC address owns 192.168.1.1?

An ARP request can be broadcast on the local network.

The owner can respond with its MAC address.
"""
)


# =============================================================================
# SECTION 39 - ICMP
# =============================================================================

title("37. ICMP")

explain(
    "ICMP - Internet Control Message Protocol",
    """
ICMP is used for network control, diagnostics, and error reporting.

Examples include:

    Echo Request
    Echo Reply
    Destination Unreachable
    Time Exceeded

The ping utility commonly uses ICMP Echo Request and Echo Reply for
diagnostic purposes.
"""
)


# =============================================================================
# SECTION 40 - PING
# =============================================================================

title("38. PING")

explain(
    "ping",
    """
ping is a network diagnostic utility.

It can test whether a destination responds to ICMP Echo Requests and can
provide round-trip timing information.

Typical command:

    ping example.com

Linux/macOS:

    ping -c 4 example.com

Windows:

    ping -n 4 example.com
"""
)

print("""
Conceptual process:

    Your Computer
         |
         | ICMP Echo Request
         v
    Destination
         |
         | ICMP Echo Reply
         v
    Your Computer

Possible outcomes:

    Reply received
    Request timed out
    Destination unreachable
    DNS resolution failure
    Packet loss
""")


# =============================================================================
# SECTION 41 - RUN PING FROM PYTHON
# =============================================================================

title("39. RUNNING PING FROM PYTHON")

system_name = platform.system().lower()

if system_name == "windows":
    ping_command = "ping -n 4 127.0.0.1"
else:
    ping_command = "ping -c 4 127.0.0.1"

run_command(ping_command)


# =============================================================================
# SECTION 42 - TRACEROUTE
# =============================================================================

title("40. TRACEROUTE / TRACERT")

explain(
    "traceroute",
    """
traceroute on Linux/macOS and tracert on Windows are diagnostic utilities
used to identify intermediate hops between a source and destination.

Windows:

    tracert example.com

Linux/macOS:

    traceroute example.com
"""
)

print("""
Conceptual path:

    Computer
       |
       | Hop 1
       v
    Router
       |
       | Hop 2
       v
    ISP Router
       |
       | Hop 3
       v
    Backbone Router
       |
       | Hop 4
       v
    Destination

Traceroute commonly relies on packets with controlled TTL values.

When a router decrements the TTL to zero, it may send an ICMP Time
Exceeded message back to the sender.

This lets the sender discover intermediate hops.
""")


# =============================================================================
# SECTION 43 - TTL
# =============================================================================

title("41. TTL")

explain(
    "TTL - Time To Live",
    """
IPv4 packets contain a TTL field.

Each router forwarding the packet normally decrements TTL.

If TTL reaches zero, the packet is discarded and an ICMP Time Exceeded
message may be generated.

This prevents packets from circulating indefinitely because of routing
loops.

Example:

    Initial TTL = 64

    Router 1 -> 63
    Router 2 -> 62
    Router 3 -> 61
    ...
"""
)


# =============================================================================
# SECTION 44 - HTTP
# =============================================================================

title("42. HTTP")

explain(
    "HTTP - Hypertext Transfer Protocol",
    """
HTTP is an application-layer protocol used for web communication.

A simplified HTTP request:

    GET /index.html HTTP/1.1
    Host: example.com

A simplified response:

    HTTP/1.1 200 OK

    <html>...</html>
"""
)


# =============================================================================
# SECTION 45 - HTTPS
# =============================================================================

title("43. HTTPS")

explain(
    "HTTPS",
    """
HTTPS is HTTP transported through a secure TLS connection.

Simplified:

    HTTP
      +
    TLS
      |
      v
    TCP
      |
      v
    IP

HTTPS provides important security properties such as:

    Encryption
    Authentication of the server
    Integrity protection
"""
)


# =============================================================================
# SECTION 46 - TLS
# =============================================================================

title("44. TLS BASICS")

explain(
    "TLS - Transport Layer Security",
    """
TLS establishes cryptographic protections for application traffic.

During a TLS handshake, the client and server negotiate cryptographic
parameters and establish keys used to protect the session.

Certificates are used to authenticate the server's identity through a
certificate authority trust system.

Modern HTTPS generally uses TLS 1.2 or TLS 1.3.

TLS protects application data in transit but does not automatically make
every endpoint trustworthy.
"""
)


# =============================================================================
# SECTION 47 - NAT
# =============================================================================

title("45. NAT")

explain(
    "NAT - Network Address Translation",
    """
NAT allows network addresses to be translated between different address
spaces.

A common home network example:

    Laptop:
        192.168.1.20:51524

    Router performs NAT

    Internet:
        Public-IP:40001

The router maintains state so replies can be associated with the internal
connection.

NAT is widely used with private IPv4 networks.
"""
)


# =============================================================================
# SECTION 48 - FIREWALLS
# =============================================================================

title("46. FIREWALL")

explain(
    "Firewall",
    """
A firewall controls traffic according to security policy.

Example rule:

    Allow TCP destination port 443

Another example:

    Block inbound TCP port 23

Firewalls can operate at different levels of sophistication.

They may inspect:

    IP addresses
    Ports
    Protocols
    Connection state
    Application data
"""
)


# =============================================================================
# SECTION 49 - PROXY
# =============================================================================

title("47. PROXY SERVER")

explain(
    "Proxy",
    """
A forward proxy acts on behalf of clients.

Conceptually:

    Client
       |
       v
    Proxy
       |
       v
    Internet

A reverse proxy sits in front of servers.

Conceptually:

    Client
       |
       v
    Reverse Proxy
       |
       +------> Server 1
       |
       +------> Server 2
       |
       +------> Server 3

Reverse proxies are commonly used for:

    Load balancing
    TLS termination
    Caching
    Routing
    Security controls
"""
)


# =============================================================================
# SECTION 50 - VPN
# =============================================================================

title("48. VPN BASICS")

explain(
    "VPN - Virtual Private Network",
    """
A VPN creates a logical protected tunnel between endpoints.

Conceptually:

    Device
       |
       | Encrypted tunnel
       v
    VPN Gateway
       |
       v
    Destination Network

VPNs can be used for:

    Remote access
    Site-to-site connectivity
    Secure communication over untrusted networks
"""
)


# =============================================================================
# SECTION 51 - SOCKET ADDRESS
# =============================================================================

title("49. SOCKET ADDRESS")

explain(
    "Socket endpoint",
    """
A network service can be represented by:

    IP address + transport protocol + port

Example:

    127.0.0.1:8080/TCP

Python can represent this using socket APIs.
"""
)


# =============================================================================
# SECTION 52 - TCP SERVER
# =============================================================================

title("50. PYTHON TCP SERVER")

print("""
Example TCP server:

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_socket.bind(("127.0.0.1", 5000))
    server_socket.listen()

    connection, address = server_socket.accept()

    data = connection.recv(1024)

    connection.sendall(b"Hello from server")

    connection.close()

Key ideas:

    AF_INET
        IPv4

    SOCK_STREAM
        TCP-style byte stream

    bind()
        Assign local address and port

    listen()
        Begin listening for incoming connections

    accept()
        Accept a connection

    recv()
        Receive bytes

    sendall()
        Send bytes
""")


# =============================================================================
# SECTION 53 - ACTUAL TCP SERVER FUNCTION
# =============================================================================

def tcp_server(host="127.0.0.1", port=5000):
    """
    Minimal TCP server.

    Run this function in one terminal.
    Then use the TCP client below from another terminal.
    """

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Allow quick reuse of the address after restart.
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((host, port))
    server.listen(5)

    print(f"TCP server listening on {host}:{port}")

    try:
        connection, address = server.accept()

        print("Client connected:", address)

        with connection:
            data = connection.recv(4096)

            print("Received:", data.decode(errors="replace"))

            response = b"Hello from Python TCP server!"
            connection.sendall(response)

    finally:
        server.close()


# =============================================================================
# SECTION 54 - TCP CLIENT
# =============================================================================

def tcp_client(host="127.0.0.1", port=5000):
    """
    Minimal TCP client.

    Start tcp_server() first.
    """

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.connect((host, port))

        client.sendall(b"Hello from Python TCP client!")

        response = client.recv(4096)

        print("Server response:", response.decode(errors="replace"))

    finally:
        client.close()


# =============================================================================
# SECTION 55 - UDP
# =============================================================================

title("51. PYTHON UDP SOCKETS")

print("""
UDP socket creation:

    udp_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

Send:

    udp_socket.sendto(
        b"Hello",
        ("127.0.0.1", 6000)
    )

Receive:

    data, address = udp_socket.recvfrom(4096)

UDP does not require TCP-style accept() and connection establishment.
""")


# =============================================================================
# SECTION 56 - UDP SERVER
# =============================================================================

def udp_server(host="127.0.0.1", port=6000):
    """
    Minimal UDP server.
    """

    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    server.bind((host, port))

    print(f"UDP server listening on {host}:{port}")

    try:
        data, address = server.recvfrom(4096)

        print("Received from:", address)
        print("Data:", data.decode(errors="replace"))

        server.sendto(
            b"Hello from UDP server!",
            address
        )

    finally:
        server.close()


# =============================================================================
# SECTION 57 - UDP CLIENT
# =============================================================================

def udp_client(host="127.0.0.1", port=6000):
    """
    Minimal UDP client.
    """

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        client.sendto(
            b"Hello from UDP client!",
            (host, port)
        )

        data, address = client.recvfrom(4096)

        print("Response:", data.decode(errors="replace"))

    finally:
        client.close()


# =============================================================================
# SECTION 58 - SOCKET INFORMATION
# =============================================================================

title("52. SOCKET INFORMATION")

hostname = socket.gethostname()
print("Hostname:", hostname)

try:
    local_ip = socket.gethostbyname(hostname)
    print("Resolved local IP:", local_ip)
except socket.gaierror:
    print("Could not resolve local hostname.")


# =============================================================================
# SECTION 59 - getaddrinfo
# =============================================================================

title("53. getaddrinfo()")

explain(
    "socket.getaddrinfo()",
    """
getaddrinfo() is a powerful API for obtaining address information suitable
for creating sockets.

It can return IPv4 and IPv6 addresses and protocol information.
"""
)

try:
    results = socket.getaddrinfo(
        "example.com",
        443,
        type=socket.SOCK_STREAM
    )

    for result in results[:5]:
        print(result)

except socket.gaierror as error:
    print("Lookup failed:", error)


# =============================================================================
# SECTION 60 - DOMAIN NAME TO IP
# =============================================================================

title("54. HOSTNAME RESOLUTION")

def resolve_hostname(hostname):
    """Resolve a hostname into available addresses."""

    try:
        results = socket.getaddrinfo(hostname, None)

        addresses = sorted(
            set(result[4][0] for result in results)
        )

        print(f"\nAddresses for {hostname}:")

        for address in addresses:
            print("  ", address)

        return addresses

    except socket.gaierror as error:
        print("Resolution failed:", error)
        return []


resolve_hostname("example.com")


# =============================================================================
# SECTION 61 - TESTING TCP PORT CONNECTIVITY
# =============================================================================

title("55. TEST TCP PORT CONNECTIVITY")

def test_tcp_port(host, port, timeout=3):
    """
    Attempt to establish a TCP connection to a host and port.

    This tests TCP connectivity, not whether an application is necessarily
    functioning correctly.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        result = sock.connect_ex((host, port))

        if result == 0:
            print(f"{host}:{port} is reachable over TCP.")
            return True

        print(
            f"{host}:{port} did not accept the TCP connection. "
            f"Error code: {result}"
        )

        return False

    except socket.gaierror:
        print("Hostname could not be resolved.")
        return False

    except socket.timeout:
        print("Connection timed out.")
        return False

    finally:
        sock.close()


# Example:
# test_tcp_port("example.com", 443)


# =============================================================================
# SECTION 62 - PING VS TCP CONNECTIVITY
# =============================================================================

title("56. PING VS TCP CONNECTION TEST")

print("""
Ping:

    Tests ICMP-based reachability/response.

TCP port test:

    Attempts to establish a TCP connection to a specific port.

Important:

A host may:

    Block ICMP
    Allow TCP 443

Therefore:

    ping fails

while:

    HTTPS works

Conversely, a host may respond to ping while a particular TCP service
is unavailable.

Therefore, ping is not a universal test for application availability.
""")


# =============================================================================
# SECTION 63 - TERMINAL NETWORK COMMANDS
# =============================================================================

title("57. IMPORTANT TERMINAL NETWORK COMMANDS")

print("""
Windows:

    ipconfig
    ipconfig /all
    ping example.com
    tracert example.com
    nslookup example.com
    arp -a
    route print
    netstat -ano

Linux:

    ip addr
    ip route
    ping example.com
    traceroute example.com
    nslookup example.com
    dig example.com
    ip neigh
    ss -tulpn
    netstat -tulpn

macOS:

    ifconfig
    netstat -rn
    ping example.com
    traceroute example.com
    nslookup example.com
    arp -a
    lsof -i
""")


# =============================================================================
# SECTION 64 - IP CONFIGURATION
# =============================================================================

title("58. ipconfig / ip addr")

print("""
Windows:

    ipconfig

Provides basic interface and IP configuration information.

For more details:

    ipconfig /all

Linux:

    ip addr

or:

    ip a

These commands can reveal:

    IP addresses
    Network interfaces
    MAC addresses
    Subnet information
    Interface state
""")


# =============================================================================
# SECTION 65 - ROUTING TABLE
# =============================================================================

title("59. VIEWING THE ROUTING TABLE")

print("""
Windows:

    route print

Linux:

    ip route

macOS:

    netstat -rn

A routing table can contain:

    Destination network
    Prefix/mask
    Gateway
    Interface
    Metric

Example:

    default via 192.168.1.1
    192.168.1.0/24 dev eth0
""")


# =============================================================================
# SECTION 66 - NETSTAT / SS
# =============================================================================

title("60. VIEWING NETWORK CONNECTIONS")

print("""
Windows:

    netstat -ano

Linux:

    ss -tulpn

These can help inspect:

    Listening ports
    Established connections
    Local addresses
    Remote addresses
    TCP states
    Process IDs (depending on OS/permissions)
""")


# =============================================================================
# SECTION 67 - TCP CONNECTION STATES
# =============================================================================

title("61. TCP STATES")

print("""
Common TCP states include:

    LISTEN
    SYN-SENT
    SYN-RECEIVED
    ESTABLISHED
    FIN-WAIT-1
    FIN-WAIT-2
    CLOSE-WAIT
    LAST-ACK
    TIME-WAIT
    CLOSED

The exact state transitions depend on the communication sequence.

ESTABLISHED generally means a TCP connection has been successfully
established.

LISTEN generally means a server socket is waiting for connections.
""")


# =============================================================================
# SECTION 68 - DNS TROUBLESHOOTING
# =============================================================================

title("62. DNS TROUBLESHOOTING")

print("""
If:

    ping 8.8.8.8

works but:

    ping example.com

fails,

DNS may be the problem.

Useful commands:

Windows:

    nslookup example.com

Linux/macOS:

    dig example.com
    nslookup example.com

The distinction is important:

    Name resolution problem

versus:

    Network connectivity problem
""")


# =============================================================================
# SECTION 69 - NETWORK TROUBLESHOOTING FLOW
# =============================================================================

title("63. NETWORK TROUBLESHOOTING METHODOLOGY")

print("""
A structured troubleshooting approach:

    Step 1:
        Check physical/Wi-Fi connection.

    Step 2:
        Check network interface configuration.

        ipconfig /all
        ip addr

    Step 3:
        Check local TCP/IP stack.

        ping 127.0.0.1

    Step 4:
        Check local gateway.

        ping <gateway>

    Step 5:
        Test external IP connectivity.

        ping <known-IP>

    Step 6:
        Test DNS.

        nslookup example.com

    Step 7:
        Test destination application port.

        TCP connection to port 443

    Step 8:
        Inspect path.

        tracert
        traceroute

    Step 9:
        Inspect local routes.

        route print
        ip route

    Step 10:
        Inspect firewall/proxy/VPN configuration.

The goal is to isolate the failing layer rather than randomly changing
settings.
""")


# =============================================================================
# SECTION 70 - PACKET LOSS
# =============================================================================

title("64. PACKET LOSS")

explain(
    "Packet loss",
    """
Packet loss occurs when transmitted packets do not successfully reach the
expected destination or are not returned as expected.

Potential causes:

    Congestion
    Wireless interference
    Faulty hardware
    Network failures
    Firewall behavior
    Routing problems
    Overloaded devices
    ISP issues

Some packet loss at intermediate traceroute hops does not necessarily mean
the destination is experiencing equivalent packet loss.

Routers may deprioritize or rate-limit diagnostic responses.
"""
)


# =============================================================================
# SECTION 71 - LATENCY
# =============================================================================

title("65. LATENCY")

explain(
    "Latency",
    """
Latency is the time required for data to travel through a communication path.

Ping commonly reports round-trip time.

For example:

    10 ms
    50 ms
    150 ms

Lower latency generally means less delay, but the acceptable value depends
on the application.

Factors include:

    Physical distance
    Propagation
    Queuing
    Processing
    Routing
    Network congestion
"""
)


# =============================================================================
# SECTION 72 - BANDWIDTH VS LATENCY
# =============================================================================

title("66. BANDWIDTH VS LATENCY")

print("""
Bandwidth:

    How much data can potentially be transferred per unit time.

Latency:

    How long communication takes.

Example:

A connection can have:

    High bandwidth
    High latency

A large file may eventually transfer quickly, but the initial response
may still experience noticeable delay.

Therefore:

    Bandwidth != Latency
""")


# =============================================================================
# SECTION 73 - JITTER
# =============================================================================

title("67. JITTER")

explain(
    "Jitter",
    """
Jitter refers to variation in packet delay.

Example:

    Packet 1 -> 20 ms
    Packet 2 -> 22 ms
    Packet 3 -> 80 ms
    Packet 4 -> 25 ms

The variation can be problematic for:

    Voice
    Video conferencing
    Real-time gaming
"""
)


# =============================================================================
# SECTION 74 - MTU
# =============================================================================

title("68. MTU")

explain(
    "MTU - Maximum Transmission Unit",
    """
MTU is the maximum packet payload size that a network interface/link can
normally carry at a given layer without fragmentation at that layer.

A common Ethernet MTU is:

    1500 bytes

Path MTU can vary.

Incorrect MTU configuration can produce difficult-to-diagnose connectivity
problems.
"""
)


# =============================================================================
# SECTION 75 - FRAGMENTATION
# =============================================================================

title("69. IP FRAGMENTATION")

explain(
    "Fragmentation",
    """
When packets are larger than a network path can accommodate, fragmentation
may occur depending on IP version and configuration.

Modern networks generally try to avoid fragmentation where possible.

Path MTU Discovery helps endpoints determine an appropriate packet size.
"""
)


# =============================================================================
# SECTION 76 - APPLICATION FLOW EXAMPLE
# =============================================================================

title("70. WHAT HAPPENS WHEN YOU OPEN A WEBSITE?")

print("""
Suppose you enter:

    https://example.com

A simplified sequence is:

    1. Browser parses the URL.

    2. Browser needs an IP address.

    3. DNS resolution occurs.

        example.com
             |
             v
        DNS Resolver
             |
             v
        IP address

    4. Client determines where to send traffic.

    5. Packets travel through local networking.

    6. Router forwards traffic toward the destination.

    7. TCP connection may be established.

    8. TLS handshake occurs for HTTPS.

    9. Browser sends HTTP request.

   10. Server sends HTTP response.

   11. Browser processes the response.

   12. Additional resources may be requested.

This entire process can happen extremely quickly.
""")


# =============================================================================
# SECTION 77 - COMPLETE LAYERED VIEW
# =============================================================================

title("71. COMPLETE NETWORK STACK EXAMPLE")

print("""
Application:

    HTTPS
       |
       v
Transport:

    TCP
       |
       v
Internet:

    IP
       |
       v
Link:

    Ethernet / Wi-Fi
       |
       v
Physical:

    Electrical / optical / radio signals

At the destination:

    Physical
       |
       v
    Link
       |
       v
    IP
       |
       v
    TCP
       |
       v
    TLS
       |
       v
    HTTP
       |
       v
    Application
""")


# =============================================================================
# SECTION 78 - URL BREAKDOWN
# =============================================================================

title("72. BREAKING DOWN A URL")

url_example = "https://example.com:443/products?id=10#details"

print("""
URL:

    https://example.com:443/products?id=10#details

Components:

    Scheme:
        https

    Host:
        example.com

    Port:
        443

    Path:
        /products

    Query:
        id=10

    Fragment:
        details

Default HTTPS port is normally:

    443

Default HTTP port is normally:

    80
""")


# =============================================================================
# SECTION 79 - SOCKET 4-TUPLE
# =============================================================================

title("73. TCP FOUR-TUPLE")

print("""
A TCP connection is commonly identified using:

    Source IP
    Source Port
    Destination IP
    Destination Port

Example:

    192.168.1.20
    51524
    93.184.216.34
    443

This helps the operating system distinguish multiple simultaneous
connections.
""")


# =============================================================================
# SECTION 80 - EPHEMERAL PORTS
# =============================================================================

title("74. EPHEMERAL PORTS")

explain(
    "Ephemeral port",
    """
When a client creates an outbound connection, the operating system commonly
selects a temporary source port.

Example:

    Client:
        192.168.1.20:51524

    Server:
        93.184.216.34:443

The client port 51524 is an example of an ephemeral port.
"""
)


# =============================================================================
# SECTION 81 - CONNECTION VS REQUEST
# =============================================================================

title("75. CONNECTION VS APPLICATION REQUEST")

print("""
A TCP connection and an HTTP request are different concepts.

One TCP connection can carry multiple HTTP requests depending on the HTTP
version and connection behavior.

Example:

    TCP connection
       |
       +--> HTTP request 1
       |
       +--> HTTP request 2
       |
       +--> HTTP request 3

Modern HTTP protocols make network communication more sophisticated than
one connection per request.
""")


# =============================================================================
# SECTION 82 - HTTP/2 AND HTTP/3
# =============================================================================

title("76. HTTP/2 AND HTTP/3")

explain(
    "HTTP/2",
    """
HTTP/2 improves web performance using mechanisms such as multiplexing,
allowing multiple streams over a single connection.

HTTP/2 commonly operates over TCP with TLS.
"""
)

explain(
    "HTTP/3",
    """
HTTP/3 uses QUIC as its transport protocol.

QUIC runs over UDP but provides transport features such as:

    Reliability
    Congestion control
    Stream multiplexing
    TLS integration
    Connection migration

HTTP/3 therefore changes the traditional:

    HTTP -> TCP -> IP

relationship into approximately:

    HTTP/3 -> QUIC -> UDP -> IP
"""
)


# =============================================================================
# SECTION 83 - QUIC
# =============================================================================

title("77. QUIC")

explain(
    "QUIC",
    """
QUIC is a modern transport protocol implemented over UDP.

It was designed to provide:

    Reliable delivery
    Congestion control
    Encryption
    Multiplexed streams
    Faster connection establishment
    Connection migration

QUIC is important for understanding modern Internet architecture.
"""
)


# =============================================================================
# SECTION 84 - INTERNET BACKBONE
# =============================================================================

title("78. INTERNET BACKBONE")

explain(
    "Internet backbone",
    """
The Internet backbone consists of high-capacity interconnected networks
that carry large volumes of traffic.

Traffic may cross:

    ISP networks
    Regional networks
    Data-center networks
    Transit providers
    Internet exchange points
    Autonomous systems

The global Internet is a collection of interconnected administrative
domains rather than a single centrally controlled network.
"""
)


# =============================================================================
# SECTION 85 - INTERNET EXCHANGE POINT
# =============================================================================

title("79. INTERNET EXCHANGE POINT")

explain(
    "IXP - Internet Exchange Point",
    """
An Internet Exchange Point allows different networks to exchange traffic
directly through shared switching infrastructure.

This can improve:

    Routing efficiency
    Latency
    Traffic localization
    Cost efficiency

IXPs are important components of Internet interconnection.
"""
)


# =============================================================================
# SECTION 86 - AUTONOMOUS SYSTEM
# =============================================================================

title("80. AUTONOMOUS SYSTEM")

explain(
    "Autonomous System",
    """
An Autonomous System, commonly identified by an ASN, is a collection of
IP networks under a common administrative and routing policy.

BGP is used to exchange routing information between autonomous systems.

Simplified:

    AS 64500
        |
        | BGP
        |
    AS 64501
        |
        | BGP
        |
    AS 64502
"""
)


# =============================================================================
# SECTION 87 - BGP
# =============================================================================

title("81. BGP")

explain(
    "BGP - Border Gateway Protocol",
    """
BGP is the principal inter-domain routing protocol used on the public
Internet.

It exchanges reachability information between autonomous systems.

BGP decisions can involve:

    Local preference
    AS path
    MED
    Communities
    Policy
    Next hop

BGP is policy-driven rather than simply choosing the geographically shortest
path.
"""
)


# =============================================================================
# SECTION 88 - ROUTING LOOP
# =============================================================================

title("82. ROUTING LOOPS")

explain(
    "Routing loop",
    """
A routing loop occurs when packets repeatedly circulate through routers
because of incorrect or inconsistent routing information.

TTL helps limit the lifetime of IPv4 packets in such situations.

Example:

    Router A
       |
       v
    Router B
       |
       v
    Router C
       |
       v
    Router A
       |
       v
    ...

TTL eventually reaches zero.
"""


# =============================================================================
# SECTION 89 - NETWORK ADDRESSING SUMMARY
# =============================================================================

title("83. ADDRESSING HIERARCHY")

print("""
A simplified addressing hierarchy:

    Application
        |
    Port
        |
    IP address
        |
    Network prefix
        |
    Local link
        |
    MAC address
        |
    Physical transmission

Different layers solve different addressing problems.
""")


# =============================================================================
# SECTION 90 - SOCKET TIMEOUT
# =============================================================================

title("84. SOCKET TIMEOUTS")

def safe_tcp_request(host, port=443, timeout=5):
    """
    Demonstrates setting a socket timeout.

    This example establishes TCP connectivity only.
    It does not perform TLS or HTTP.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        print(f"Connecting to {host}:{port}...")

        sock.connect((host, port))

        print("TCP connection established.")

        return True

    except socket.timeout:
        print("Connection timed out.")
        return False

    except socket.gaierror:
        print("DNS resolution failed.")
        return False

    except OSError as error:
        print("Socket error:", error)
        return False

    finally:
        sock.close()


# Example:
# safe_tcp_request("example.com", 443)


# =============================================================================
# SECTION 91 - SOCKET OPTIONS
# =============================================================================

title("85. SOCKET OPTIONS")

print("""
Python sockets provide APIs for configuring behavior.

Example:

    socket.settimeout(5)

    socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

Socket programming requires understanding:

    Address family
    Socket type
    Blocking vs non-blocking behavior
    Timeouts
    Connection lifecycle
    Error handling
    Resource cleanup
""")


# =============================================================================
# SECTION 92 - BLOCKING VS NON-BLOCKING
# =============================================================================

title("86. BLOCKING VS NON-BLOCKING SOCKETS")

explain(
    "Blocking socket",
    """
A blocking socket waits for an operation to complete.

For example:

    recv()

may wait until data is available.
"""
)

explain(
    "Non-blocking socket",
    """
A non-blocking socket returns control to the program instead of waiting
indefinitely.

Non-blocking sockets are useful for:

    Event loops
    High-concurrency servers
    Asynchronous networking
    Network frameworks
"""
)


# =============================================================================
# SECTION 93 - SELECT
# =============================================================================

title("87. SOCKET MULTIPLEXING")

print("""
Python's select module can be used to monitor multiple sockets.

Conceptual pattern:

    while True:

        readable, writable, exceptional = select(...)

        for socket in readable:
            process(socket)

Modern Python applications may instead use:

    asyncio

or frameworks built on asynchronous event loops.
""")


# =============================================================================
# SECTION 94 - NETWORK SECURITY
# =============================================================================

title("88. BASIC NETWORK SECURITY")

print("""
Important network security principles:

    1. Minimize exposed services.

    2. Use HTTPS instead of unencrypted HTTP where appropriate.

    3. Avoid legacy insecure protocols.

    4. Use strong authentication.

    5. Keep operating systems and network devices updated.

    6. Use firewalls.

    7. Segment sensitive networks.

    8. Monitor network activity.

    9. Encrypt sensitive traffic.

   10. Do not assume that an IP address alone establishes identity.
""")


# =============================================================================
# SECTION 95 - DNS SECURITY
# =============================================================================

title("89. DNS SECURITY")

print("""
DNS can be attacked or manipulated through mechanisms such as:

    DNS spoofing
    DNS cache poisoning
    Malicious DNS infrastructure
    Domain hijacking

Security-related technologies include:

    DNSSEC
    DoH
    DoT

Important distinction:

    DNSSEC protects authenticity/integrity of DNS data.

    DoH/DoT protect DNS queries in transit between client and resolver.

These technologies solve different problems.
""")


# =============================================================================
# SECTION 96 - PACKET CAPTURE
# =============================================================================

title("90. PACKET CAPTURE")

explain(
    "Packet capture",
    """
Tools such as Wireshark can capture and inspect network packets.

Packet analysis can reveal:

    Source/destination addresses
    Protocols
    Ports
    TCP handshakes
    DNS queries
    Retransmissions
    TLS handshakes
    Packet timing

Packet capture is one of the most powerful techniques for advanced network
troubleshooting.

Use packet capture only on networks and systems where you have authorization.
"""
)


# =============================================================================
# SECTION 97 - NETWORK TROUBLESHOOTING DECISION TREE
# =============================================================================

title("91. ADVANCED TROUBLESHOOTING DECISION TREE")

print("""
Problem:
    Website does not load.

        |
        v
Can DNS resolve the domain?
        |
       NO
        |
        +--> Investigate DNS configuration
        |
       YES
        |
        v
Can you reach the network gateway?
        |
       NO
        |
        +--> Investigate local network
        |
       YES
        |
        v
Can you reach external network?
        |
       NO
        |
        +--> Investigate routing/ISP/firewall
        |
       YES
        |
        v
Can TCP connect to port 443?
        |
       NO
        |
        +--> Investigate firewall/service/path
        |
       YES
        |
        v
Does TLS handshake succeed?
        |
       NO
        |
        +--> Investigate TLS/certificates/time/proxy
        |
       YES
        |
        v
Does HTTP request succeed?
        |
       NO
        |
        +--> Investigate HTTP/application layer
        |
       YES
        |
        v
Application problem may be above the network layer.
""")


# =============================================================================
# SECTION 98 - COMMON NETWORK MISTAKES
# =============================================================================

title("92. COMMON BEGINNER MISTAKES")

print("""
Mistake 1:
    Thinking the Internet and Web are identical.

Correction:
    The Web is a service running over the Internet.

Mistake 2:
    Thinking an IP address identifies a physical computer permanently.

Correction:
    IP addressing is logical and can change.

Mistake 3:
    Thinking ping proves a website is working.

Correction:
    Ping tests ICMP behavior, not the full application stack.

Mistake 4:
    Thinking port 443 automatically means HTTPS.

Correction:
    Port numbers are conventions. Services can use other ports.

Mistake 5:
    Thinking routers use MAC addresses for global Internet routing.

Correction:
    IP addresses are used for Layer 3 routing; MAC addressing is local-link
    addressing.

Mistake 6:
    Thinking packet loss from one traceroute hop always means that router
    is dropping transit traffic.

Correction:
    Intermediate routers may rate-limit diagnostic responses.

Mistake 7:
    Thinking TCP and UDP are application protocols.

Correction:
    They are transport-layer protocols.

Mistake 8:
    Thinking DNS is only a website lookup system.

Correction:
    DNS supports many record types and Internet naming functions.
""")


# =============================================================================
# SECTION 99 - PRACTICAL COMMAND CHEAT SHEET
# =============================================================================

title("93. PRACTICAL COMMAND CHEAT SHEET")

print("""
WINDOWS

IP configuration:
    ipconfig
    ipconfig /all

Connectivity:
    ping 8.8.8.8

DNS:
    nslookup example.com

Path:
    tracert example.com

ARP:
    arp -a

Routes:
    route print

Connections:
    netstat -ano


LINUX

IP configuration:
    ip addr

Routes:
    ip route

Connectivity:
    ping example.com

DNS:
    dig example.com
    nslookup example.com

Path:
    traceroute example.com

Neighbor table:
    ip neigh

Connections:
    ss -tulpn


MACOS

IP configuration:
    ifconfig

Routes:
    netstat -rn

Connectivity:
    ping example.com

DNS:
    dig example.com

Path:
    traceroute example.com

ARP:
    arp -a

Connections:
    lsof -i
""")


# =============================================================================
# SECTION 100 - PRACTICAL LABS
# =============================================================================

title("94. PRACTICAL LAB EXERCISES")

print("""
LAB 1 - Identify your IP configuration

Windows:
    ipconfig /all

Linux:
    ip addr

macOS:
    ifconfig


LAB 2 - Identify your routing table

Windows:
    route print

Linux:
    ip route

macOS:
    netstat -rn


LAB 3 - Test localhost

    ping 127.0.0.1


LAB 4 - Test your gateway

    ping <default-gateway>


LAB 5 - Test DNS

    nslookup example.com


LAB 6 - Trace a route

Windows:
    tracert example.com

Linux/macOS:
    traceroute example.com


LAB 7 - Inspect TCP connections

Windows:
    netstat -ano

Linux:
    ss -tulpn


LAB 8 - Python DNS lookup

    socket.gethostbyname("example.com")


LAB 9 - Python TCP server

    Start tcp_server()

Then from another Python process:

    tcp_client()


LAB 10 - Python UDP server

    Start udp_server()

Then:

    udp_client()
""")


# =============================================================================
# SECTION 101 - KNOWLEDGE CHECK
# =============================================================================

title("95. KNOWLEDGE CHECK")

questions = [
    "What is the difference between the Internet and the Web?",
    "What does an ISP do?",
    "What is an IP address?",
    "What is the difference between IPv4 and IPv6?",
    "What is a private IP address?",
    "What is a MAC address?",
    "What is a subnet?",
    "What is CIDR?",
    "What is a default gateway?",
    "What does DNS do?",
    "What does DHCP do?",
    "What is routing?",
    "What is a routing table?",
    "What is longest prefix match?",
    "What is a port?",
    "What is a socket?",
    "What is TCP?",
    "What is UDP?",
    "What is the TCP three-way handshake?",
    "What is ICMP?",
    "How does ping work conceptually?",
    "What does traceroute/tracert do?",
    "What is TTL?",
    "What is NAT?",
    "What is a firewall?",
    "What is HTTPS?",
    "What is TLS?",
    "What is packet loss?",
    "What is latency?",
    "What is jitter?",
    "What is MTU?",
    "What is BGP?",
    "What is an Autonomous System?",
    "What is an Internet Exchange Point?",
    "What is a TCP four-tuple?",
]

for number, question in enumerate(questions, start=1):
    print(f"{number}. {question}")


# =============================================================================
# SECTION 102 - ANSWER SUMMARY
# =============================================================================

title("96. ANSWER SUMMARY")

answers = {
    "Internet": "Global interconnected system of networks.",
    "ISP": "Organization that provides Internet/network connectivity.",
    "Packet": "Formatted unit of network-layer data.",
    "IP address": "Logical network-layer address used for communication.",
    "MAC address": "Data-link address used for local network communication.",
    "DNS": "Maps names to addresses and stores other DNS information.",
    "DHCP": "Automatically provides network configuration.",
    "Router": "Forwards packets between IP networks.",
    "Port": "Transport-layer logical endpoint number.",
    "Socket": "Programming abstraction for network communication.",
    "TCP": "Reliable, ordered, connection-oriented transport protocol.",
    "UDP": "Connectionless transport protocol with minimal built-in guarantees.",
    "ICMP": "Protocol used for diagnostics and network control.",
    "Ping": "Utility commonly using ICMP Echo for reachability/timing tests.",
    "Traceroute": "Utility that discovers/estimates intermediate network hops.",
    "TTL": "Limits packet lifetime through hop counting.",
    "NAT": "Translates addresses between network address spaces.",
    "Firewall": "Controls network traffic according to security policy.",
    "BGP": "Inter-domain routing protocol used between autonomous systems.",
}

for key, value in answers.items():
    print(f"{key:20} -> {value}")


# =============================================================================
# SECTION 103 - MENTAL MODEL
# =============================================================================

title("97. THE COMPLETE INTERNET MENTAL MODEL")

print("""
When you enter:

    https://example.com

Think:

    URL
     |
     v
    DNS
     |
     v
    IP address
     |
     v
    Routing
     |
     v
    Local gateway
     |
     v
    ISP
     |
     v
    Multiple networks / routers
     |
     v
    Destination network
     |
     v
    Server IP
     |
     v
    TCP or QUIC connection
     |
     v
    TLS
     |
     v
    HTTP
     |
     v
    Application response

At every stage, different protocols and layers solve different problems.

DNS answers:

    "What address corresponds to this name?"

IP answers:

    "Where should this packet go?"

Routing answers:

    "Which next hop should receive this packet?"

TCP answers:

    "How can we reliably exchange an ordered byte stream?"

UDP answers:

    "How can we send datagrams with minimal transport overhead?"

TLS answers:

    "How can application traffic be cryptographically protected?"

HTTP answers:

    "What application-level request/response should be exchanged?"

Sockets answer:

    "How does the application program access network communication?"

This layered mental model is one of the most important concepts in
networking.
""")


# =============================================================================
# SECTION 104 - FINAL TAKEAWAY
# =============================================================================

title("98. FINAL TAKEAWAY")

print("""
Internet fundamentals are easier to understand when the concepts are
connected rather than memorized independently.

The essential chain is:

    Device
       |
    Network Interface
       |
    MAC Address
       |
    Local Network
       |
    IP Address
       |
    Default Gateway
       |
    Router
       |
    ISP
       |
    Internet
       |
    Routing
       |
    Destination IP
       |
    Port
       |
    Socket
       |
    TCP / UDP / QUIC
       |
    Application Protocol
       |
    Service

The most important distinction to remember is:

    IP identifies the network-layer endpoint.

    Port identifies a transport-layer service endpoint.

    Socket provides a programming interface for network communication.

    TCP provides reliable ordered transport.

    UDP provides lightweight datagram transport.

    DNS resolves names.

    Routers forward packets.

    ISPs provide connectivity.

    Packets carry network-layer data.

    ping tests reachability/round-trip behavior using ICMP.

    traceroute/tracert helps reveal the path through intermediate hops.

    TCP/IP provides the practical protocol architecture underlying
    Internet communication.

Once these concepts are understood, more advanced topics become much easier:

    Network security
    Cloud networking
    APIs
    Distributed systems
    Kubernetes networking
    Load balancing
    Microservices
    Service meshes
    VPNs
    Firewalls
    Zero Trust
    BGP
    SDN
    CDN architecture
    Network monitoring
    Packet analysis
    Infrastructure engineering
    Site reliability engineering
    Cybersecurity

The Internet is not magic.

It is a layered system of protocols, addresses, packets, interfaces,
routers, services, and applications working together according to
well-defined rules.
""")


# =============================================================================
# SECTION 105 - SCRIPT COMPLETION
# =============================================================================

title("LEARNING COMPLETE")

print("""
You have completed the Internet Fundamentals Python learning module.

Recommended next topics:

    1. Computer Networking Fundamentals
    2. Subnetting and CIDR
    3. TCP/IP in greater depth
    4. DNS architecture
    5. HTTP/HTTPS
    6. Network security
    7. Linux networking
    8. Wireshark and packet analysis
    9. REST APIs
   10. Cloud networking
   11. Docker networking
   12. Kubernetes networking
   13. Load balancers
   14. Reverse proxies
   15. BGP and advanced routing
   16. Network automation with Python
   17. Network monitoring and observability
   18. Zero Trust networking
   19. SDN and modern network architecture
   20. Distributed systems networking

Keep experimenting.

Read routing tables.
Run ping.
Run traceroute/tracert.
Inspect sockets.
Write TCP clients and servers.
Resolve DNS names.
Study packet captures.

Networking becomes intuitive through observation and experimentation.
""")
