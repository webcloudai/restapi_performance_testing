/**
 * © 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
 * MIT License 
*/

import {
  APIGatewayProxyEvent, APIGatewayProxyResult,
} from 'aws-lambda';

/**
 * Lambda Handler - the entry point for API GW invocations
 *
 * @param {APIGatewayProxyEvent} event - event generated by API GW
 * @returns Promise<APIGatewayProxyResult>
 */
export const lambdaHandler = async ( event: APIGatewayProxyEvent ): Promise<APIGatewayProxyResult> => {
  await new Promise(f => setTimeout(f, 300));
  // stringify incoming event
  let eventStr:string = "";
  try {
    eventStr = JSON.stringify(event);
  } catch (error) {
    return new Promise<APIGatewayProxyResult>((resolve, reject)=> {
        resolve({
            statusCode: 500,
            body: "fail to stringify incoming event",
            isBase64Encoded: false
        });
    });
  }

  return new Promise<APIGatewayProxyResult>((resolve, reject)=> {
    resolve({
        statusCode: 200,
        body: eventStr,
        isBase64Encoded: false
    });
  });
};