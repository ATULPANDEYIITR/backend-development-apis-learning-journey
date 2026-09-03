# Internet Fundamentals

## Introduction

The Internet is a global system of interconnected computer networks that allows computers, phones, servers, cloud platforms, applications, IoT devices, and other systems to communicate with each other.

The Internet is not a single computer or a single network. It is a collection of interconnected networks operated by different organizations and connected through routers, switches, fiber-optic cables, wireless systems, data centers, Internet Service Providers (ISPs), and standardized communication protocols.

A simplified communication path is:

```text
Computer
   |
Router
   |
ISP
   |
Internet
   |
Destination ISP
   |
Destination Server
```

Understanding Internet Fundamentals is essential for learning:

* Software development
* Backend development
* Cloud computing
* DevOps
* Cybersecurity
* Distributed systems
* APIs
* Networking
* System administration
* Site reliability engineering
* Infrastructure engineering

---

## 1. Internet vs World Wide Web

The Internet and the World Wide Web are not the same thing.

The **Internet** is the underlying global networking infrastructure.

The **World Wide Web** is a service that operates on top of the Internet.

Other services that use the Internet include:

* Web browsing
* Email
* DNS
* Online gaming
* Video conferencing
* File transfer
* Streaming
* APIs
* Cloud services
* Voice communication

Therefore:

```text
Internet != Web
```

The Web primarily uses HTTP and HTTPS, while other Internet services use different protocols.

---

## 2. Client and server

A **client** is a system that requests a resource or service.

Examples include:

* Web browser
* Mobile application
* Python program
* Desktop application
* Email application

A **server** provides resources or services.

Examples include:

* Web server
* API server
* Database server
* DNS server
* Email server
* File server

A simplified interaction is:

```text
Client
   |
   | Request
   v
Server
   |
   | Response
   v
Client
```

The same physical computer can sometimes operate as both a client and a server depending on the application.

---

## 3. ISP

ISP stands for **Internet Service Provider**.

An ISP provides connectivity between a user's local network and the wider Internet.

An ISP may provide:

* Internet connectivity
* IP address assignment
* DNS services
* Routing
* Broadband
* Fiber connectivity
* Mobile Internet

A simplified architecture is:

```text
Laptop
   |
Wi-Fi
   |
Router
   |
ISP
   |
Internet
```

---

## 4. Network devices

Important networking devices include:

### Modem

A modem connects a local network to certain types of ISP infrastructure.

### Router

A router forwards packets between different networks.

### Switch

A switch connects devices within a local network.

### Access point

An access point provides wireless network connectivity.

### Firewall

A firewall controls network traffic according to security rules.

A typical home network may look like:

```text
Laptop
   |
Phone
   |
Smart TV
   |
Wi-Fi Router
   |
ISP
   |
Internet
```

---

# 5. IP addresses

An **IP address** is a logical address used for network-layer communication.

IPv4 addresses contain 32 bits.

Example:

```text
192.168.1.10
```

An IPv4 address contains four octets:

```text
192 . 168 . 1 . 10
```

Each octet contains 8 bits.

Therefore:

```text
8 + 8 + 8 + 8 = 32 bits
```

IPv4 provides:

```text
2^32 = 4,294,967,296
```

possible address values.

---

## 6. IPv4

IPv4 addresses are normally written using dotted-decimal notation.

Example:

```text
192.168.1.25
```

The binary representation is:

```text
11000000.10101000.00000001.00011001
```

IPv4 is still widely used, although the growth of the Internet led to the development and deployment of IPv6.

---

# 7. IPv6

IPv6 uses 128-bit addresses.

Example:

```text
2001:db8::1
```

An expanded representation can look like:

```text
2001:0db8:0000:0000:0000:0000:0000:0001
```

IPv6 uses hexadecimal notation and provides a vastly larger address space than IPv4.

The fundamental difference is:

```text
IPv4 -> 32 bits
IPv6 -> 128 bits
```

---

# 8. Public and private IP addresses

Private IPv4 address ranges include:

```text
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
```

A home network might look like:

```text
Router:
192.168.1.1

Laptop:
192.168.1.10

Phone:
192.168.1.11

Smart TV:
192.168.1.12
```

These devices can communicate inside the local network.

The router commonly uses NAT to allow private devices to communicate with the public Internet.

---

# 9. IP address vs MAC address

An IP address and a MAC address serve different purposes.

### IP address

Used primarily for logical network communication and routing.

### MAC address

Used primarily at the link layer for communication on the local network.

A useful mental model is:

```text
IP  = logical network addressing

MAC = local link-layer identification
```

Example MAC address:

```text
00:1A:2B:3C:4D:5E
```

---

# 10. DNS

DNS stands for **Domain Name System**.

Humans prefer names such as:

```text
example.com
```

Network communication ultimately requires addresses.

DNS maps domain names to network information, including IP addresses.

Conceptually:

```text
example.com
     |
     v
    DNS
     |
     v
IP address
```

Important DNS record types include:

| Record | Purpose                    |
| ------ | -------------------------- |
| A      | IPv4 address               |
| AAAA   | IPv6 address               |
| CNAME  | Canonical name             |
| MX     | Mail server                |
| NS     | Name server                |
| TXT    | Text information           |
| SOA    | Zone authority information |

DNS is one of the fundamental services that makes the Internet practical to use.

---

# 11. Packets

Data transmitted over networks is divided into smaller units.

At the IP layer, these are generally called **packets**.

Conceptually:

```text
Large Data
    |
    +---- Packet 1
    +---- Packet 2
    +---- Packet 3
    +---- Packet 4
```

Packets contain addressing and control information appropriate to their protocol layers.

Breaking data into packets makes it possible for many communications to share network infrastructure.

---

# 12. Packet switching

The Internet uses packet-switched networking.

Multiple users can share network infrastructure:

```text
User A ----\
             \
User B ------ Router ------ Internet
             /
User C ----/
```

Routers forward packets based on routing information.

Packets belonging to a communication can encounter different conditions as they travel through the network.

---

# 13. Routing

**Routing** is the process of determining where packets should be forwarded.

Routers maintain routing information.

A simplified routing table could look like:

```text
Destination        Next Hop
--------------------------------
192.168.1.0/24     Local
10.0.0.0/8         Router A
172.16.0.0/12      Router B
0.0.0.0/0          ISP
```

The route:

```text
0.0.0.0/0
```

is commonly known as the default route for IPv4.

It is used when no more specific route matches.

---

# 14. Router

A router connects different IP networks.

Example:

```text
Network A
192.168.1.0/24
      |
    Router
      |
Network B
10.0.0.0/24
```

The router examines the destination address and determines where the packet should be forwarded.

Routers are therefore fundamental to Internet communication.

---

# 15. Default gateway

A **default gateway** is normally the router a device uses to reach destinations outside its local network.

Example:

```text
Laptop IP:
192.168.1.20

Default Gateway:
192.168.1.1
```

If the laptop wants to communicate with another local device:

```text
192.168.1.30
```

the communication may remain inside the local network.

If it wants to communicate with:

```text
8.8.8.8
```

the packet normally goes through the default gateway.

---

# 16. Ports

An IP address identifies a network destination.

A **port** identifies an application or service endpoint within that host.

Port numbers range from:

```text
0 to 65535
```

Some commonly associated ports are:

| Port | Common service |
| ---: | -------------- |
|   22 | SSH            |
|   53 | DNS            |
|   80 | HTTP           |
|  443 | HTTPS          |

A network endpoint can therefore be represented as:

```text
IP address + port
```

Example:

```text
192.168.1.20:443
```

---

# 17. Sockets

A **socket** is a programming interface and communication endpoint used by applications for network communication.

A TCP communication can conceptually be identified by:

```text
Source IP
Source Port
Destination IP
Destination Port
Protocol
```

For example:

```text
Client:
192.168.1.10:51000

Server:
192.168.1.20:443
```

Python provides socket programming through its built-in `socket` module.

---

# 18. TCP

TCP stands for **Transmission Control Protocol**.

TCP provides reliable, ordered byte-stream communication.

Important characteristics include:

* Connection-oriented communication
* Reliable delivery
* Ordered data
* Retransmission
* Flow control
* Congestion control

TCP is commonly used where reliable delivery is important.

Examples include:

* HTTPS over TCP
* SSH
* Database connections
* Many traditional application protocols

An important programming concept is:

> TCP is a byte stream.

A single `send()` operation does not necessarily correspond to a single `recv()` operation.

Applications must correctly handle partial reads and writes.

---

# 19. TCP three-way handshake

TCP connection establishment uses a three-way handshake.

Simplified:

```text
Client                       Server

  SYN ---------------------->

      <---------------------- SYN + ACK

  ACK ---------------------->
```

The connection is then established.

The three messages involve:

* SYN
* SYN + ACK
* ACK

The real TCP state machine is more detailed, but this model is essential for understanding TCP.

---

# 20. TCP reliability

TCP provides reliability using mechanisms such as:

* Sequence numbers
* Acknowledgments
* Retransmissions
* Checksums
* Flow control
* Congestion control

For example:

```text
Sender:

Packet 1
Packet 2
Packet 3

Receiver:

ACK 1
ACK 2
ACK 3
```

If a packet is lost, TCP can retransmit the missing data.

TCP reliability does not mean the Internet itself never loses packets. It means TCP implements mechanisms to provide reliable delivery to the application when possible.

---

# 21. UDP

UDP stands for **User Datagram Protocol**.

UDP is connectionless and lightweight.

Characteristics include:

* No TCP-style connection establishment
* No built-in reliable delivery
* No built-in ordering guarantee
* Lower protocol overhead
* Datagram-based communication

UDP can be useful for:

* DNS
* Real-time applications
* Gaming
* Streaming-related protocols
* QUIC

UDP itself does not guarantee delivery.

---

# 22. TCP vs UDP

| Feature             | TCP         | UDP      |
| ------------------- | ----------- | -------- |
| Connection-oriented | Yes         | No       |
| Reliable delivery   | Yes         | No       |
| Ordered byte stream | Yes         | No       |
| Retransmission      | Yes         | No       |
| Protocol overhead   | Higher      | Lower    |
| Data model          | Byte stream | Datagram |

The correct protocol depends on application requirements.

---

# 23. TCP/IP model

A commonly taught TCP/IP model consists of four layers:

```text
1. Application
2. Transport
3. Internet
4. Network Access
```

Example:

```text
Application
HTTP

Transport
TCP

Internet
IP

Network Access
Ethernet / Wi-Fi
```

Each layer has a specific responsibility.

---

# 24. Encapsulation

When application data is transmitted, each networking layer adds information required by that layer.

Conceptually:

```text
Application Data
       |
       v
TCP Segment
       |
       v
IP Packet
       |
       v
Link-Layer Frame
```

At the destination, the process is reversed.

This is called **decapsulation**.

The layered model allows applications to communicate without needing to implement every lower-level networking mechanism themselves.

---

# 25. HTTP and HTTPS

HTTP stands for **Hypertext Transfer Protocol**.

HTTPS means HTTP secured using TLS.

HTTPS commonly uses port:

```text
443
```

A simplified HTTPS communication flow is:

```text
Browser
   |
DNS
   |
IP address
   |
Transport connection
   |
TLS
   |
HTTPS request
   |
Web server
   |
HTTPS response
```

---

# 26. NAT

NAT stands for **Network Address Translation**.

NAT commonly allows multiple private devices to share a public IPv4 address.

Example:

```text
Laptop
192.168.1.10:50000
       |
       v
    Router
       |
       v
Public-IP:62000
       |
       v
Internet Server
```

NAT and firewalls are related in many network designs but are not the same technology.

NAT translates addresses and possibly ports.

A firewall enforces traffic-control rules.

---

# 27. DHCP

DHCP stands for **Dynamic Host Configuration Protocol**.

DHCP can automatically provide network configuration such as:

* IP address
* Subnet mask/prefix
* Default gateway
* DNS server

A common conceptual DHCP process is:

```text
Discover
   |
Offer
   |
Request
   |
Acknowledge
```

This is commonly called **DORA**.

DHCP is why many devices can automatically obtain network configuration without manual IP assignment.

---

# 28. ARP

ARP stands for **Address Resolution Protocol**.

In IPv4 local networks, ARP can be used to discover the MAC address associated with an IPv4 address.

Conceptually:

```text
IPv4 address
     |
     v
    ARP
     |
     v
MAC address
```

IPv6 uses Neighbor Discovery instead of ARP.

---

# 29. Subnetting

Subnetting divides an IP address space into network and host portions.

Example:

```text
192.168.1.0/24
```

The `/24` means:

```text
24 bits = network prefix
8 bits  = remaining address bits
```

There are:

```text
2^8 = 256
```

IPv4 addresses in the block.

In a traditional subnet model, two addresses are generally reserved for network and broadcast purposes:

```text
256 - 2 = 254 usable host addresses
```

The exact usable-address model depends on the addressing situation.

---

# 30. CIDR

CIDR stands for **Classless Inter-Domain Routing**.

Examples:

```text
10.0.0.0/8
172.16.0.0/12
192.168.1.0/24
192.168.1.0/26
```

The number after `/` represents the prefix length.

A larger prefix length generally means a smaller address block.

For example:

```text
/26
```

represents a smaller IPv4 block than:

```text
/24
```

---

# 31. Latency

**Latency** is the time required for data to travel through a network path.

It is commonly measured in milliseconds.

Factors affecting latency include:

* Physical distance
* Routing path
* Congestion
* Queuing
* Processing
* Wireless conditions

Lower latency generally means better responsiveness.

---

# 32. Bandwidth

**Bandwidth** represents the maximum data-carrying capacity of a network connection.

Examples:

```text
100 Mbps
1 Gbps
10 Gbps
```

Bandwidth is not the same as actual transfer speed.

A connection advertised as 1 Gbps may deliver less than 1 Gbps of application-level throughput.

---

# 33. Throughput

**Throughput** represents the actual rate of successful data transfer.

Example:

```text
Link capacity:
1 Gbps

Actual throughput:
700 Mbps
```

Therefore:

```text
Bandwidth != Throughput
```

---

# 34. Packet loss

Packet loss occurs when packets fail to reach their destination.

Possible causes include:

* Network congestion
* Hardware failures
* Wireless interference
* Routing problems
* Configuration problems
* Overloaded systems

Packet loss can result in:

* TCP retransmissions
* Lower throughput
* Increased application delays
* Poor audio/video quality

---

# 35. Jitter

**Jitter** refers to variation in packet delay.

Example:

```text
Packet 1 -> 20 ms
Packet 2 -> 22 ms
Packet 3 -> 80 ms
Packet 4 -> 21 ms
```

The large variation in delay can be problematic for real-time applications such as:

* Voice calls
* Video conferencing
* Online gaming
* Real-time streaming

---

# 36. Firewalls

A firewall controls network traffic according to configured rules.

Rules can consider:

* Source IP
* Destination IP
* Protocol
* Source port
* Destination port
* Connection state

A conceptual rule could be:

```text
Allow TCP destination port 443
```

This could permit HTTPS traffic.

Firewalls can exist on:

* Individual computers
* Routers
* Dedicated appliances
* Cloud platforms
* Network security systems

---

# 37. ICMP

ICMP stands for **Internet Control Message Protocol**.

It is used for network-layer control and diagnostic messaging.

Examples include:

* Echo Request
* Echo Reply
* Destination Unreachable
* Time Exceeded

`ping` commonly uses ICMP Echo Request and Echo Reply.

Traceroute can use ICMP responses depending on its implementation.

---

# 38. Ping

`ping` is a network diagnostic utility.

Example on Windows:

```text
ping example.com
```

Linux/macOS:

```text
ping example.com
```

Ping can help determine:

* Whether a destination responds
* Approximate round-trip time
* Packet loss

A simplified model is:

```text
Computer
   |
ICMP Echo Request
   |
Destination
   |
ICMP Echo Reply
   |
Computer
```

A failed ping does not necessarily prove that a host is offline.

A firewall or network policy may block ICMP.

---

# 39. Tracert and traceroute

Windows commonly uses:

```text
tracert example.com
```

Linux/macOS commonly use:

```text
traceroute example.com
```

Traceroute helps reveal the network path toward a destination.

A simplified path might be:

```text
Computer
   |
Router 1
   |
Router 2
   |
Router 3
   |
Router 4
   |
Server
```

Each router represents a network hop.

Some routers intentionally do not respond to traceroute probes.

Therefore output such as:

```text
* * *
```

does not automatically mean that the path is broken.

---

# 40. TTL

TTL stands for **Time To Live**.

In IPv4, TTL is a field in the IP header.

Routers normally decrement the TTL when forwarding a packet.

Conceptually:

```text
TTL = 5

Router 1 -> TTL 4
Router 2 -> TTL 3
Router 3 -> TTL 2
Router 4 -> TTL 1
Router 5 -> TTL 0
```

When TTL reaches zero, the packet is discarded.

This prevents packets from circulating indefinitely.

---

# 41. How traceroute works

Traceroute takes advantage of TTL behavior.

Conceptually:

```text
TTL = 1
    |
    v
Router 1 responds

TTL = 2
    |
    v
Router 2 responds

TTL = 3
    |
    v
Router 3 responds

TTL = 4
    |
    v
Router 4 responds

TTL = 5
    |
    v
Destination responds
```

By progressively increasing the TTL, traceroute can identify intermediate hops.

Actual implementations differ between operating systems and traceroute modes.

---

# 42. Useful terminal commands

## Windows

```text
ipconfig
ipconfig /all
ping <host>
tracert <host>
nslookup <domain>
arp -a
route print
netstat -ano
```

## Linux

```text
ip addr
ip route
ping <host>
traceroute <host>
nslookup <domain>
dig <domain>
ss -tuln
ip neigh
```

## macOS

Commonly useful commands include:

```text
ifconfig
ping <host>
traceroute <host>
nslookup <domain>
dig <domain>
netstat
```

---

# 43. Python networking

Python provides networking capabilities through the standard `socket` module.

A hostname can be resolved using:

```python
import socket

hostname = "example.com"

ip_address = socket.gethostbyname(hostname)

print(ip_address)
```

This demonstrates basic DNS resolution.

---

# 44. Python TCP socket

A TCP client can conceptually perform:

```text
socket()
   |
connect()
   |
send()
   |
receive()
   |
close()
```

A simplified Python example is:

```python
import socket

host = "example.com"
port = 443

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    client.settimeout(5)
    client.connect((host, port))

    print("Connected successfully.")
```

The example should only be used against systems you are authorized to access.

---

# 45. Python TCP server

A TCP server generally performs:

```text
socket()
   |
bind()
   |
listen()
   |
accept()
   |
receive/send
   |
close()
```

A simplified local server:

```python
import socket

HOST = "127.0.0.1"
PORT = 5000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"Listening on {HOST}:{PORT}")

    connection, address = server.accept()

    with connection:
        print("Client:", address)

        data = connection.recv(1024)

        print("Received:", data.decode("utf-8", errors="replace"))

        connection.sendall(b"Message received.")
```

Using `127.0.0.1` keeps this example local.

---

# 46. UDP socket programming

UDP uses datagrams instead of a TCP-style byte stream.

Example:

```python
import socket

host = "127.0.0.1"
port = 5001

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.sendto(
        b"Hello using UDP",
        (host, port)
    )
```

UDP does not establish a TCP-style connection before sending the datagram.

---

# 47. Socket endpoint

A socket endpoint can be represented as:

```text
IP address + Port
```

Example:

```text
127.0.0.1:5000
```

Here:

```text
127.0.0.1 = IP address
5000      = Port
```

`127.0.0.1` is the IPv4 loopback address.

IPv6 loopback is:

```text
::1
```

---

# 48. Network timeouts

Network operations should generally use reasonable timeouts.

Example:

```python
sock.settimeout(5)
```

Without timeouts, network operations may wait longer than the application expects.

Timeout handling is especially important in production applications.

---

# 49. Network exceptions

Python networking code should handle failures.

Examples include:

```python
import socket

try:
    with socket.create_connection(
        ("example.com", 443),
        timeout=5
    ):
        print("Connected.")

except socket.timeout:
    print("Connection timed out.")

except socket.gaierror:
    print("DNS resolution failed.")

except ConnectionRefusedError:
    print("Connection refused.")

except OSError as error:
    print("Network error:", error)
```

Good network programs should anticipate:

* DNS failures
* Connection timeouts
* Connection refusal
* Network interruptions
* Invalid addresses
* Server failures

---

# 50. TCP is a byte stream

One of the most important concepts in socket programming is that TCP provides a byte stream.

Suppose a sender performs:

```python
send(b"Hello")
send(b"World")
```

The receiver should not assume that it will necessarily receive:

```text
Hello
World
```

It could receive data in chunks such as:

```text
Hel
loWo
rld
```

or:

```text
HelloWorld
```

or other valid segmentation.

Applications must implement appropriate message framing.

Possible framing strategies include:

* Fixed-size messages
* Length-prefix framing
* Delimiter-based framing
* Structured serialization

---

# 51. TCP connection lifecycle

A simplified TCP lifecycle is:

```text
Client                       Server

  SYN ---------------------->

      <---------------------- SYN + ACK

  ACK ---------------------->

  DATA --------------------->

      <---------------------- DATA

  FIN ---------------------->

      <---------------------- ACK

      <---------------------- FIN

  ACK ---------------------->
```

The actual TCP state machine includes additional states and edge cases.

---

# 52. What happens when you enter a website URL?

Suppose the user enters:

```text
https://example.com
```

A simplified process is:

```text
1. Browser parses the URL
2. DNS resolution determines an IP address
3. Transport communication is established
4. TLS is negotiated for HTTPS
5. Browser sends an HTTP request
6. Server processes the request
7. Server returns an HTTP response
8. Browser processes and renders the response
```

The real process can involve:

* Browser cache
* DNS cache
* Operating-system cache
* DNS resolver
* CDN
* Load balancer
* Proxy
* Firewall
* NAT
* Multiple routers
* TLS
* HTTP/2
* HTTP/3
* QUIC

---

# 53. DNS caching

DNS results can be cached at several levels:

* Browser
* Operating system
* Local DNS resolver
* Enterprise DNS infrastructure
* ISP resolver

Caching reduces repeated DNS queries and can improve performance.

DNS records contain TTL values that influence caching behavior.

---

# 54. Routing table and longest-prefix matching

Routing tables can contain multiple matching routes.

Example:

```text
10.0.0.0/8
10.10.0.0/16
```

For destination:

```text
10.10.5.20
```

both routes match.

The `/16` route is more specific than `/8`.

Routing generally prefers the most specific matching prefix.

This concept is called **longest-prefix matching**.

---

# 55. Autonomous Systems

An **Autonomous System (AS)** is a collection of IP networks and routers under a common administrative control and routing policy.

The Internet can be conceptually represented as:

```text
AS 1
 |
 | BGP
 v
AS 2
 |
 | BGP
 v
AS 3
```

BGP stands for **Border Gateway Protocol**.

BGP is the principal inter-domain routing protocol used to exchange network reachability information between autonomous systems.

---

# 56. Interior routing protocols

Inside organizations and networks, different routing protocols may be used.

Examples include:

* OSPF
* IS-IS
* EIGRP

The exact protocol depends on the network architecture and operational requirements.

This creates an important distinction:

```text
Inside an organization
        |
Interior routing

Between autonomous systems
        |
BGP
```

---

# 57. Anycast

Anycast allows the same IP address to be announced from multiple network locations.

A client can then be routed toward a suitable location according to network routing.

Anycast is commonly used in distributed services such as:

* DNS infrastructure
* CDNs
* Edge services

---

# 58. CDN

CDN stands for **Content Delivery Network**.

A CDN distributes content across geographically distributed edge locations.

Instead of every user contacting one central server:

```text
User A ----\
User B ----- CDN Edge
User C ----/
```

This can improve:

* Latency
* Scalability
* Availability
* Origin-server load

---

# 59. Load balancing

A load balancer distributes requests among multiple backend servers.

Example:

```text
             Load Balancer
              /    |    \
             /     |     \
        Server A Server B Server C
```

Load balancing can improve:

* Scalability
* Availability
* Resource utilization
* Fault tolerance

---

# 60. Reverse proxy

A reverse proxy sits between clients and backend servers.

```text
Client
   |
   v
Reverse Proxy
   |
   +---- Backend A
   |
   +---- Backend B
   |
   +---- Backend C
```

A reverse proxy can provide:

* TLS termination
* Routing
* Caching
* Compression
* Security controls
* Load balancing

---

# 61. Forward proxy vs reverse proxy

### Forward proxy

```text
Client
   |
Proxy
   |
Internet
```

The proxy acts on behalf of the client.

### Reverse proxy

```text
Internet
   |
Reverse Proxy
   |
Backend Servers
```

The reverse proxy acts on behalf of the server infrastructure.

---

# 62. MTU

MTU stands for **Maximum Transmission Unit**.

It represents the maximum size of a packet/frame payload that can be transmitted over a particular network link without fragmentation at that layer.

A commonly encountered Ethernet MTU is:

```text
1500 bytes
```

Actual MTU depends on the networking technology and configuration.

Incorrect MTU configuration can cause connectivity problems.

---

# 63. Fragmentation

If an IPv4 packet is too large for a link and fragmentation is allowed, it can be divided into smaller fragments.

IPv6 routers do not fragment packets in transit.

Modern networks generally attempt to avoid unnecessary fragmentation.

MTU and Path MTU Discovery are therefore important concepts in advanced networking.

---

# 64. TLS

TLS stands for **Transport Layer Security**.

TLS provides cryptographic protection for network communications.

It can provide:

* Confidentiality
* Integrity
* Authentication

HTTPS commonly uses TLS.

A simplified model is:

```text
Application
    |
   TLS
    |
Transport
    |
   IP
```

Certificate validation is an important part of secure TLS communication.

---

# 65. HTTP/1.1, HTTP/2 and HTTP/3

### HTTP/1.1

A traditional version of HTTP commonly used over TCP.

### HTTP/2

Provides features such as:

* Multiplexing
* Binary framing
* Header compression

### HTTP/3

Uses QUIC as its transport.

Conceptually:

```text
HTTP/1.1 -> TCP
HTTP/2   -> TCP
HTTP/3   -> QUIC -> UDP
```

---

# 66. QUIC

QUIC is a modern transport protocol implemented over UDP.

It provides transport features such as:

* Reliable streams
* Encryption integration
* Multiplexing
* Connection migration capabilities

HTTP/3 uses QUIC.

This demonstrates an important concept:

```text
UDP itself does not provide TCP-style reliability.

A protocol built over UDP can implement
its own reliability and transport features.
```

---

# 67. Network troubleshooting methodology

When a website or application is not working, troubleshooting should be systematic.

A useful sequence is:

```text
1. Check physical/Wi-Fi connectivity
2. Check local IP configuration
3. Check default gateway
4. Test local gateway
5. Test external IP connectivity
6. Test DNS resolution
7. Test destination port
8. Use traceroute/tracert
9. Check firewall/proxy/VPN
10. Examine routing and packet loss
```

Example:

```text
ping 192.168.1.1
```

If this fails, the problem may be local.

Then:

```text
ping 8.8.8.8
```

If the gateway works but this fails, the problem may be upstream.

Then:

```text
nslookup example.com
```

If IP connectivity works but DNS resolution fails, DNS may be the problem.

Finally, test the actual service such as TCP port 443.

---

# 68. Troubleshooting decision tree

```text
Website not opening
        |
        v
Does the machine have an IP?
        |
       / \
     No   Yes
     |      |
Check DHCP  v
       Can gateway be reached?
             |
            / \
          No   Yes
          |      |
    Check local  v
      network   Can public IP be reached?
                    |
                   / \
                 No   Yes
                 |      |
           Check ISP/   v
           routing/  Does DNS work?
           firewall      |
                        / \
                      No   Yes
                      |      |
                  Check DNS  v
                         Can destination
                         TCP port connect?
                              |
                             / \
                           No   Yes
                           |      |
                    Service or    |
                    firewall      |
                    issue         v
                              Investigate
                              HTTPS/TLS/
                              application
```

---

# 69. Important networking distinctions

Understanding the difference between similar terms is essential.

| Concept    | Meaning                                      |
| ---------- | -------------------------------------------- |
| Internet   | Global interconnected network of networks    |
| ISP        | Provider of Internet connectivity/services   |
| IP         | Logical network-layer addressing             |
| IPv4       | 32-bit IP addressing                         |
| IPv6       | 128-bit IP addressing                        |
| MAC        | Link-layer interface identifier              |
| Packet     | Network-layer data unit                      |
| Router     | Forwards packets between networks            |
| Switch     | Connects devices within a network            |
| Gateway    | Device used to reach other networks          |
| DNS        | Resolves names into network information      |
| Port       | Application/service endpoint                 |
| Socket     | Application communication endpoint/interface |
| TCP        | Reliable ordered byte-stream transport       |
| UDP        | Connectionless datagram transport            |
| ICMP       | Network control/diagnostic protocol          |
| NAT        | Network address translation                  |
| DHCP       | Dynamic network configuration                |
| Ping       | Connectivity/latency diagnostic              |
| Traceroute | Network-path diagnostic                      |

---

# 70. Essential terminal commands

## Windows

```text
ipconfig
ipconfig /all
ping 8.8.8.8
ping example.com
tracert example.com
nslookup example.com
arp -a
route print
netstat -ano
```

## Linux

```text
ip addr
ip route
ping 8.8.8.8
ping example.com
traceroute example.com
nslookup example.com
dig example.com
ip neigh
ss -tuln
```

These commands help inspect:

* IP configuration
* Routing
* DNS
* Network reachability
* Open listening ports
* Neighbor information
* Network path

---

# 71. Advanced network architecture

A modern Internet-facing application may look like:

```text
                    Internet
                       |
                       v
                    DNS/CDN
                       |
                       v
                 Load Balancer
                       |
                       v
                 Reverse Proxy
                       |
          +------------+------------+
          |            |            |
          v            v            v
      App Server   App Server   App Server
          |            |            |
          +------------+------------+
                       |
                       v
                    Database
```

Additional infrastructure may include:

* Firewalls
* API gateways
* Service meshes
* Caches
* Message queues
* Object storage
* Monitoring
* Logging
* Identity systems
* Secrets management
* VPNs
* Cloud networking

---

# 72. Internet communication mental model

A powerful mental model is:

```text
Application
    |
    v
Port
    |
    v
Socket
    |
    v
TCP / UDP / QUIC
    |
    v
IP
    |
    v
Routing
    |
    v
Packet
    |
    v
Router
    |
    v
ISP
    |
    v
Internet
    |
    v
Destination Network
    |
    v
Destination Server
```

This model connects almost every fundamental networking concept.

---

# 73. What I learned

By studying Internet Fundamentals, I learned that Internet communication is a layered process involving many different technologies.

I learned that the Internet is a global network of interconnected networks rather than one centralized system.

I learned the role of an ISP and how a user's local network connects to the wider Internet.

I learned the difference between the Internet and the World Wide Web.

I learned how clients communicate with servers using standardized protocols.

I learned what IP addresses are and how IPv4 differs from IPv6.

I learned the difference between public and private IP addresses.

I learned the role of MAC addresses at the link layer.

I learned how DNS converts human-readable domain names into network information.

I learned that network communication is divided into packets.

I learned how packet switching allows many communications to share network infrastructure.

I learned how routers forward packets between networks.

I learned the purpose of the default gateway.

I learned that ports identify application and service endpoints.

I learned what sockets are and how applications use them for network communication.

I learned the difference between TCP and UDP.

I learned the TCP three-way handshake.

I learned how TCP provides reliability through acknowledgments, sequence numbers, retransmissions, flow control, and congestion control.

I learned that TCP is a byte stream and that applications cannot assume one send operation equals one receive operation.

I learned how the TCP/IP model organizes networking responsibilities into layers.

I learned the concepts of encapsulation and decapsulation.

I learned the roles of HTTP and HTTPS.

I learned what NAT does and why private networks commonly use it.

I learned how DHCP automatically provides network configuration.

I learned how ARP maps IPv4 addresses to link-layer addresses on local networks.

I learned subnetting and CIDR notation.

I learned the difference between bandwidth and throughput.

I learned what latency, packet loss, and jitter mean.

I learned what ICMP is and how it is used for network diagnostics.

I learned how `ping` can be used to test reachability and approximate round-trip time.

I learned how `tracert` and `traceroute` help identify network hops.

I learned how TTL works and how traceroute uses TTL behavior to identify intermediate network devices.

I learned how to use terminal commands such as `ipconfig`, `ip`, `ping`, `tracert`, `traceroute`, `nslookup`, `dig`, `arp`, `route`, and `ss`.

I learned how Python's `socket` module can be used for TCP and UDP networking.

I learned how to create TCP clients and servers.

I learned how to use socket timeouts and exception handling.

I learned about DNS caching, routing tables, longest-prefix matching, autonomous systems, BGP, CDN architecture, load balancing, reverse proxies, TLS, HTTP/2, HTTP/3, QUIC, MTU, and fragmentation.

Most importantly, I learned how to think about networking as a layered system:

```text
Application
     ↓
Transport
     ↓
Internet
     ↓
Network Access
     ↓
Physical Network
```

---

# 74. Final takeaway

The most important lesson from Internet Fundamentals is that when an application communicates across the Internet, many layers work together.

A simplified journey is:

```text
Application
    ↓
Socket
    ↓
Port
    ↓
TCP / UDP / QUIC
    ↓
IP
    ↓
Packet
    ↓
Router
    ↓
ISP
    ↓
Internet
    ↓
Destination Network
    ↓
Server
```

Once this mental model is clear, more advanced areas such as cloud networking, distributed systems, APIs, cybersecurity, DevOps, Kubernetes networking, service meshes, VPNs, BGP, CDN architecture, network security, and large-scale system design become much easier to understand.

The fundamental principle is:

> **Applications communicate through protocols, protocols operate in layers, packets carry the communication, IP provides logical addressing, routers move packets between networks, and the global collection of interconnected networks forms the Internet.**

This foundation provides the networking knowledge required to progress toward backend engineering, cloud engineering, DevOps, cybersecurity, distributed systems, and infrastructure engineering.

```
```

