// HTTPServer.swift: a small local HTTP server on Apple's Network framework (a building block from plm; it
// compiles as it is, so change your own files, not this one).
//
//     let server = try HTTPServer(port: 3118) { request in
//         if request.path == "/" { return .html("<h1>hello</h1>") }
//         if request.path == "/speed", let v = request.query["value"] { return .json("{\"speed\": \(v)}") }
//         return .notFound
//     }
//     server.start()
//
// The handler runs on a background queue: hop to the main queue (DispatchQueue.main.async) before touching UI
// state or Bluetooth objects. Other devices on the same network reach it at http://<this Mac's address>:<port>/.

import Foundation
import Network

struct HTTPRequest {
    let method: String             // "GET", "POST", ...
    let path: String               // "/speed", without the query
    let query: [String: String]    // ?car=1&value=300 -> ["car": "1", "value": "300"]
    let headers: [String: String]  // names in lower case
    let body: Data

    var bodyText: String { String(decoding: body, as: UTF8.self) }
}

struct HTTPResponse {
    var status = 200
    var contentType = "text/plain; charset=utf-8"
    var body = Data()

    static func text(_ string: String, status: Int = 200) -> HTTPResponse {
        HTTPResponse(status: status, contentType: "text/plain; charset=utf-8", body: Data(string.utf8))
    }

    static func html(_ string: String) -> HTTPResponse {
        HTTPResponse(status: 200, contentType: "text/html; charset=utf-8", body: Data(string.utf8))
    }

    static func json(_ string: String, status: Int = 200) -> HTTPResponse {
        HTTPResponse(status: status, contentType: "application/json", body: Data(string.utf8))
    }

    static let notFound = HTTPResponse.text("not found", status: 404)
}

final class HTTPServer {
    private let listener: NWListener
    private let handler: (HTTPRequest) -> HTTPResponse
    private let queue = DispatchQueue(label: "plm.http-server")

    init(port: UInt16, handler: @escaping (HTTPRequest) -> HTTPResponse) throws {
        guard let port = NWEndpoint.Port(rawValue: port) else {
            throw NSError(domain: "HTTPServer", code: 1, userInfo: [NSLocalizedDescriptionKey: "invalid port"])
        }
        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true
        listener = try NWListener(using: parameters, on: port)
        self.handler = handler
    }

    func start() {
        listener.newConnectionHandler = { [weak self] connection in
            guard let self else { return }
            connection.start(queue: self.queue)
            self.receive(on: connection, buffer: Data())
        }
        listener.start(queue: queue)
    }

    func stop() {
        listener.cancel()
    }

    private func receive(on connection: NWConnection, buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, isComplete, error in
            guard let self else { return }
            var buffer = buffer
            if let data { buffer.append(data) }
            if let request = HTTPServer.parse(buffer) {
                self.send(self.handler(request), on: connection)
            } else if isComplete || error != nil || buffer.count > 2_000_000 {
                connection.cancel()
            } else {
                self.receive(on: connection, buffer: buffer)
            }
        }
    }

    private func send(_ response: HTTPResponse, on connection: NWConnection) {
        let reason = [200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"][response.status] ?? "OK"
        var head = "HTTP/1.1 \(response.status) \(reason)\r\n"
        head += "Content-Type: \(response.contentType)\r\n"
        head += "Content-Length: \(response.body.count)\r\n"
        head += "Access-Control-Allow-Origin: *\r\n"
        head += "Connection: close\r\n\r\n"
        connection.send(content: Data(head.utf8) + response.body, completion: .contentProcessed { _ in
            connection.cancel()
        })
    }

    /// The request in `data`, or nil while it is still incomplete.
    private static func parse(_ data: Data) -> HTTPRequest? {
        guard let headerEnd = data.range(of: Data("\r\n\r\n".utf8)) else { return nil }
        let head = String(decoding: data[data.startIndex..<headerEnd.lowerBound], as: UTF8.self)
        let lines = head.components(separatedBy: "\r\n")
        let parts = (lines.first ?? "").split(separator: " ")
        guard parts.count >= 2 else { return nil }
        var headers: [String: String] = [:]
        for line in lines.dropFirst() {
            guard let colon = line.firstIndex(of: ":") else { continue }
            headers[line[..<colon].lowercased()] = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
        }
        let length = Int(headers["content-length"] ?? "0") ?? 0
        let bodyStart = headerEnd.upperBound
        guard data.endIndex - bodyStart >= length else { return nil }
        let target = String(parts[1])
        let pieces = target.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)
        var query: [String: String] = [:]
        if pieces.count > 1 {
            for pair in pieces[1].split(separator: "&") {
                let kv = pair.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
                let key = String(kv[0]).removingPercentEncoding ?? String(kv[0])
                let value = kv.count > 1 ? String(kv[1]).replacingOccurrences(of: "+", with: " ") : ""
                query[key] = value.removingPercentEncoding ?? value
            }
        }
        return HTTPRequest(method: String(parts[0]), path: String(pieces[0]), query: query, headers: headers,
                           body: Data(data[bodyStart..<(bodyStart + length)]))
    }
}
