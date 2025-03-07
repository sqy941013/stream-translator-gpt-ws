const WebSocket = require('ws');
const chalk = require('chalk');

// WebSocket connection URL
const WS_URL = 'ws://192.168.123.1:23456';

// Create WebSocket connection
const ws = new WebSocket(WS_URL);

// Connection opened
ws.on('open', () => {
    console.log(chalk.green('✓ Connected to WebSocket server'));
    console.log(chalk.cyan(`Server URL: ${WS_URL}`));
    console.log(chalk.yellow('Waiting for messages...\n'));
});

// Listen for messages
ws.on('message', (data) => {
    try {
        const message = JSON.parse(data);
        
        // Print timestamp if available
        if (message.timestamp) {
            console.log(chalk.gray(`[${message.timestamp}]`));
        }
        
        // Print transcribed text if available
        if (message.transcribed_text) {
            console.log(chalk.blue('Original:'));
            console.log(chalk.blue(message.transcribed_text));
        }
        
        // Print translated text
        if (message.translated_text) {
            console.log(chalk.green('Translation:'));
            console.log(chalk.green(message.translated_text));
        }
        
        // Print time range
        if (message.time_range) {
            console.log(chalk.gray(`Time range: ${message.time_range[0]}s - ${message.time_range[1]}s`));
        }
        
        console.log('-------------------\n');
    } catch (error) {
        console.error(chalk.red('Error parsing message:'), error);
        console.error(chalk.red('Raw message:'), data.toString());
    }
});

// Handle errors
ws.on('error', (error) => {
    console.error(chalk.red('WebSocket error:'), error);
});

// Handle connection close
ws.on('close', () => {
    console.log(chalk.yellow('⚠ Disconnected from WebSocket server'));
});

// Handle process termination
process.on('SIGINT', () => {
    console.log(chalk.yellow('\nClosing WebSocket connection...'));
    ws.close();
    process.exit(0);
});
