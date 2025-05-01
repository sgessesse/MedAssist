'use client'; // Required for components with hooks like useState, useEffect

import React, { useState, useRef, useEffect } from 'react';

// Define message structure
interface Message {
  id: number;
  sender: 'user' | 'assistant';
  text: string;
  sources?: { title?: string; url?: string; source?: string }[];
  triageTag?: string | null; // Add optional triageTag field
}

const initialWelcomeMessage: Message = {
  id: 0, // Static ID for the initial message
  sender: 'assistant',
  text: "Welcome to MedAssist! I can help you with general medical questions, provide basic symptom triage suggestions, schedule appointments (for registered users), and set reminders. \n\n**Disclaimer:** I am an AI assistant and cannot provide medical advice. My suggestions are for informational purposes only and are not a substitute for consulting a qualified healthcare professional. For emergencies, please call 911 or go to the nearest emergency room.",
  triageTag: null, // No triage tag for the welcome message
};

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([initialWelcomeMessage]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>(''); // State for unique user ID
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null); // Ref for scrolling

  // Retrieve backend URL from environment variable
  const backendApiUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000/api/v1/chat'; // Fallback for local dev

  // Generate unique user ID on component mount
  useEffect(() => {
    // Use crypto.randomUUID for a standard UUID
    // Add a fallback for older environments if necessary, though unlikely for modern React dev
    const generatedUserId = typeof window !== 'undefined' && window.crypto?.randomUUID ? window.crypto.randomUUID() : `guest-${Date.now()}`;
    setUserId(generatedUserId);
    console.log("Generated User ID:", generatedUserId); // Log for debugging

    // Initialize session ID (or keep it null until first response)
    // setSessionId(null); // Already defaults to null

  }, []); // Empty dependency array ensures this runs only once on mount

  // Function to scroll to the bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]); // Scroll whenever messages update

  const handleSendMessage = async () => {
    const trimmedMessage = inputMessage.trim();
    if (!trimmedMessage || !userId) return;

    const newUserMessage: Message = {
      id: Date.now(), // Simple ID generation
      sender: 'user',
      text: trimmedMessage,
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      // Use the environment variable for the API URL
      const apiUrl = backendApiUrl;

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          message: trimmedMessage,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        // Try to get error details from response body
        let errorDetail = `HTTP error! Status: ${response.status}`;
        try {
            const errorData = await response.json();
            errorDetail = errorData.detail || JSON.stringify(errorData) || errorDetail;
        } catch /* (jsonError) - Removed unused variable */ {
             // Ignore if response body is not valid JSON
        }
        throw new Error(errorDetail);
      }

      const data = await response.json();

      const assistantMessage: Message = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: data.reply,
        sources: data.sources, // Add sources if available
        triageTag: data.triage_tag, // Store the triage tag from the response
      };

      setMessages((prev) => [...prev, assistantMessage]);
      // Update session ID if it's the first response in a session
      if (!sessionId && data.session_id) {
        setSessionId(data.session_id);
      }

    } 
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    catch (err: any) {
      console.error('Failed to send message:', err);
      setError(`Failed to get response: ${err.message}`);
      // Optionally add the error message back to the chat
      setMessages((prev) => [...prev, { id: Date.now()+2, sender: 'assistant', text: `Error: ${err.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Enter key press in input
  const handleKeyPress = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !isLoading) {
      handleSendMessage();
    }
  };

  // Helper function to get background color class based on triage tag
  const getAssistantMessageBgColor = (tag: string | null | undefined): string => {
    switch (tag) {
      case 'SelfCare':
        return 'bg-yellow-100'; // Light yellow
      case 'DoctorSoon':
        return 'bg-orange-100'; // Light orange
      case 'ER':
        return 'bg-red-200'; // Changed to slightly darker red
      default:
        return 'bg-white'; // Default background
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */} 
      <header className="bg-blue-600 text-white p-4 shadow-md">
        <h1 className="text-xl font-semibold">MedAssist Chat</h1>
      </header>

      {/* Message List - Add bottom padding */} 
      <div className="flex-1 overflow-y-auto p-4 space-y-4 pb-10">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              // Dynamically set background color for assistant messages
              className={`max-w-lg lg:max-w-xl px-4 py-2 rounded-lg shadow ${ 
                msg.sender === 'user' 
                  ? 'bg-blue-500 text-white' 
                  : `${getAssistantMessageBgColor(msg.triageTag)} text-gray-800` 
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
              {/* Display Sources */} 
              {msg.sender === 'assistant' && msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-300/50 text-sm">
                  <p className="font-semibold mb-1">Sources:</p>
                  <ul className="list-disc list-inside space-y-1">
                    {msg.sources.map((source, index) => (
                      <li key={index}>
                        {source.url ? (
                          <a 
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-200 hover:underline"
                          >
                            {source.title || source.source || source.url}
                          </a>
                        ) : (
                          <span>{source.title || source.source}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
        {/* Loading Indicator */} 
        {isLoading && (
          <div className="flex justify-start">
            <div className="px-4 py-2 rounded-lg shadow bg-white text-gray-500 italic">
              Assistant is thinking...
            </div>
          </div>
        )}
         {/* Error Message */} 
         {error && (
          <div className="flex justify-center">
            <div className="px-4 py-2 rounded-lg shadow bg-red-100 text-red-700">
              {error}
            </div>
          </div>
        )}
        {/* Invisible element to scroll to */} 
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */} 
      <div className="p-4 bg-white border-t border-gray-200 shadow-inner">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask MedAssist..."
            disabled={isLoading}
            className="flex-1 border border-gray-300 rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-gray-900"
          />
          <button
            onClick={handleSendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className="bg-blue-600 text-white rounded-full p-2 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {/* Simple Send Icon (Heroicons) */} 
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface; 