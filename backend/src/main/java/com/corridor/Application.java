package com.corridor;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import jakarta.servlet.http.HttpServletRequest;

@SpringBootApplication
@RestController
public class Application {
    private final RestClient research;
    public Application(@Value("${research.url:http://localhost:8000}") String url) {
        research = RestClient.builder().baseUrl(url).build();
    }
    public static void main(String[] args) { SpringApplication.run(Application.class, args); }

    @RequestMapping(value="/api/**", method={RequestMethod.GET,RequestMethod.POST})
    public ResponseEntity<byte[]> proxy(HttpServletRequest request, @RequestBody(required=false) byte[] body) {
        var uri = request.getRequestURI() + (request.getQueryString()==null ? "" : "?"+request.getQueryString());
        try {
            var call = research.method(HttpMethod.valueOf(request.getMethod())).uri(uri);
            if (body != null) call.contentType(MediaType.APPLICATION_JSON).body(body);
            return call.exchange((req,res) -> ResponseEntity.status(res.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON).body(res.getBody().readAllBytes()));
        } catch (Exception e) {
            return ResponseEntity.status(503).contentType(MediaType.APPLICATION_JSON)
                .body("{\"detail\":\"Research service unavailable. Check its health and startup logs.\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }
}
