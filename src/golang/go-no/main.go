/**
* © 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
* MIT License
 */
package main

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func handleRequest(ctx context.Context, event events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
	// Serialize the event to JSON to use as the object content
	eventJSON, err := json.Marshal(event)
	if err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error marshaling event to JSON: %w", err)
	}

	return events.APIGatewayProxyResponse{Body: string(eventJSON), StatusCode: 200}, nil
}

func main() {
	lambda.Start(handleRequest)
}
