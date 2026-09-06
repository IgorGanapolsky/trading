FROM golang:1.24-alpine@sha256:8bee1901f1e530bfb4a7850aa7a479d17ae3a18beb6e09064ed54cfd245b7191 AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -o adk-orchestrator ./cmd/trading_orchestrator

FROM alpine:3.22@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce

WORKDIR /app

COPY --from=builder /app/adk-orchestrator .

RUN apk --no-cache add ca-certificates

EXPOSE 8080 8091

CMD ["./adk-orchestrator"]
