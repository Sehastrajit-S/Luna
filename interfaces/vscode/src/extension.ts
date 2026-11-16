import * as vscode from 'vscode';
import { LunaChatViewProvider } from './lunaPanel';

export function activate(context: vscode.ExtensionContext) {
    const provider = new LunaChatViewProvider(context);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(LunaChatViewProvider.viewTypeSecondary, provider, {
            webviewOptions: { retainContextWhenHidden: true },
        })
    );

    const focusLuna = () => {
        vscode.commands.executeCommand('workbench.action.focusAuxiliaryBar');
        vscode.commands.executeCommand('luna.chatViewSecondary.focus');
    };

    context.subscriptions.push(
        vscode.commands.registerCommand('luna.openChat', focusLuna)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('luna.newChat', () => {
            provider.newConversation();
            focusLuna();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('luna.askAboutSelection', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const text = editor.document.getText(editor.selection).trim();
            if (!text) { vscode.window.showInformationMessage('Select some code first.'); return; }
            const lang = editor.document.languageId;
            provider.sendUserMessage(`What does this ${lang} code do?\n\`\`\`${lang}\n${text}\n\`\`\``);
            focusLuna();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('luna.explainCode', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const text = editor.document.getText(editor.selection).trim();
            if (!text) { vscode.window.showInformationMessage('Select some code first.'); return; }
            const lang = editor.document.languageId;
            provider.sendUserMessage(`Explain this ${lang} code step by step:\n\`\`\`${lang}\n${text}\n\`\`\``);
            focusLuna();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('luna.fixCode', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const text = editor.document.getText(editor.selection).trim();
            if (!text) { vscode.window.showInformationMessage('Select some code first.'); return; }
            const lang = editor.document.languageId;
            const file = editor.document.fileName.split(/[\\/]/).pop() ?? '';
            provider.sendUserMessage(`Fix any bugs or issues in this ${lang} code from ${file}:\n\`\`\`${lang}\n${text}\n\`\`\``);
            focusLuna();
        })
    );
}

export function deactivate() {}
