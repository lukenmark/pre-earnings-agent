from datetime import datetime
from pydantic import BaseModel


class MBPPerson(BaseModel):
    name: str
    title: str
    career_history: str
    prior_company_outcomes: str
    sec_enforcement_issues: str
    other_board_seats: list[str]
    ownership_stake: str


class ManagementBackgroundProfile(BaseModel):
    ticker: str
    people: list[MBPPerson]
    corporate_lineage: str
    related_party_transactions: str
    capital_markets_behavior: str
    auditor_history: str
    agent_opinion: str
    generated_at: datetime
    data_sources: list[str]
