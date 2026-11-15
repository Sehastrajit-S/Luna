"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const lunaPanel_1 = require("./lunaPanel");
function activate(context) {
    const provider = new lunaPanel_1.LunaChatViewProvider(context);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(lunaPanel_1.LunaChatViewProvider.viewTypeSecondary, provider, {
        webviewOptions: { retainContextWhenHidden: true },
    }));
    const focusLuna = () => {
        vscode.commands.executeCommand('workbench.action.focusAuxiliaryBar');
        vscode.commands.executeCommand('luna.chatViewSecondary.focus');
    };
    context.subscriptions.push(vscode.commands.registerCommand('luna.openChat', focusLuna));
    context.subscriptions.push(vscode.commands.registerCommand('luna.newChat', () => {
        provider.newConversation();
        focusLuna();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('luna.askAboutSelection', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor)
            return;
        const text = editor.document.getText(editor.selection).trim();
        if (!text) {
            vscode.window.showInformationMessage('Select some code first.');
            return;
        }
        const lang = editor.document.languageId;
        provider.sendUserMessage(`What does this ${lang} code do?\n\`\`\`${lang}\n${text}\n\`\`\``);
        focusLuna();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('luna.explainCode', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor)
            return;
        const text = editor.document.getText(editor.selection).trim();
        if (!text) {
            vscode.window.showInformationMessage('Select some code first.');
            return;
        }
        const lang = editor.document.languageId;
        provider.sendUserMessage(`Explain this ${lang} code step by step:\n\`\`\`${lang}\n${text}\n\`\`\``);
        focusLuna();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('luna.fixCode', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor)
            return;
        const text = editor.document.getText(editor.selection).trim();
        if (!text) {
            vscode.window.showInformationMessage('Select some code first.');
            return;
        }
        const lang = editor.document.languageId;
        const file = editor.document.fileName.split(/[\\/]/).pop() ?? '';
        provider.sendUserMessage(`Fix any bugs or issues in this ${lang} code from ${file}:\n\`\`\`${lang}\n${text}\n\`\`\``);
        focusLuna();
    }));
}
function deactivate() { }
//# sourceMappingURL=extension.js.map