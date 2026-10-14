#!/bin/bash
# Script de lancement du Microservices Matrix Analyzer

PORT=${1:-8080}
python3 server.py "$PORT"
