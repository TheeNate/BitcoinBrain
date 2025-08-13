# Overview

The Bitcoin Knowledge Store API is a FastAPI service designed to ingest Bitcoin analysis PDFs from AWS S3, process them into searchable chunks with vector embeddings, and store them in Supabase for semantic search capabilities. This system serves as a knowledge base for daily market analysis, allowing users to search through historical Bitcoin analysis documents using natural language queries.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes

## 2025-08-13 - Major Bug Fixes and Stability Improvements
- Fixed all LSP type errors across the codebase with proper None client checks
- Resolved AWS region parsing issue - added function to extract clean region codes from descriptive text
- Fixed port conflict issues by properly restarting workflows
- Ensured all services (Supabase, S3, OpenAI) initialize correctly
- App now runs successfully with all endpoints operational
- Added robust error handling for missing credentials with clear user guidance

# System Architecture

## Backend Framework
The application is built on **FastAPI** with async support throughout the stack. This choice enables high-performance concurrent operations for PDF processing, embedding generation, and database operations. The async architecture is particularly beneficial when dealing with external API calls to OpenAI and AWS services.

## Data Storage Architecture
- **Primary Database**: Supabase (PostgreSQL) with pgvector extension for storing document metadata, text chunks, and vector embeddings
- **File Storage**: AWS S3 for storing original PDF documents
- **Vector Search**: Leverages Supabase's built-in vector similarity search capabilities with 1536-dimensional embeddings

The database schema includes four main tables:
- `documents`: PDF metadata and processing status
- `doc_chunks`: Searchable text chunks with vector embeddings
- `tables_extracted`: Extracted data tables for future use
- `observations`: Daily analysis logging

## Text Processing Pipeline
The system implements a sophisticated multi-stage text processing pipeline:

1. **PDF Extraction**: Uses pdfplumber for reliable text extraction with table detection
2. **Intelligent Chunking**: Implements token-aware chunking using tiktoken for accurate token counting, respecting paragraph boundaries and maintaining context overlap
3. **Text Cleaning**: Multi-step cleaning process including OCR error correction, whitespace normalization, and security sanitization
4. **Vector Embedding**: Generates embeddings using OpenAI's text-embedding-3-small model with batch processing and retry logic

## Rate Limiting & Security
- **In-memory rate limiting**: Custom middleware implementing sliding window rate limiting per IP address
- **Input validation**: Comprehensive Pydantic schemas with security checks for S3 keys and user inputs
- **CORS configuration**: Specifically configured for ChatGPT and development environments
- **Text sanitization**: XSS prevention through HTML entity encoding and tag removal

## API Design
RESTful API design with tool-specific endpoints:
- `/tool/ingest_document`: Processes PDFs into searchable chunks
- `/tool/search_knowledge`: Semantic search across document chunks
- `/tool/list_documents`: Document discovery and metadata retrieval
- `/tool/log_observation`: Daily analysis logging

## Configuration Management
Centralized configuration system using environment variables for:
- External service credentials (Supabase, OpenAI, AWS)
- Processing parameters (chunk sizes, token limits)
- Rate limiting settings
- Search result configurations

# External Dependencies

## Core Services
- **Supabase**: PostgreSQL database with vector search capabilities using pgvector extension
- **OpenAI API**: Text embedding generation using text-embedding-3-small model (1536 dimensions)
- **AWS S3**: PDF document storage and retrieval

## Python Libraries
- **FastAPI**: Web framework with async support
- **pdfplumber**: PDF text extraction with table detection
- **tiktoken**: Accurate token counting for OpenAI models
- **boto3**: AWS SDK for S3 operations
- **httpx**: Async HTTP client for external API calls
- **pydantic**: Data validation and serialization
- **uvicorn**: ASGI server for production deployment

## Authentication & Access
- **Supabase Service Role Key**: Full database access for backend operations
- **OpenAI API Key**: Embedding generation service access
- **AWS Credentials**: S3 bucket access for PDF storage

## Development & Deployment
- **Environment Variables**: All sensitive configuration managed through environment variables
- **CORS Support**: Configured for ChatGPT integration and local development
- **Logging**: Structured logging throughout the application for monitoring and debugging