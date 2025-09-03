import React from 'react';

type StatCardProps = {
  title: string;
  value: string;
  icon?: React.ReactNode;
};

const StatCard = ({ title, value, icon }: StatCardProps) => {
  return (
    <div className="bg-white p-6 rounded-lg shadow-lg flex items-center">
      {icon && <div className="mr-4 text-blue-500">{icon}</div>}
      <div>
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-800">{value}</p>
      </div>
    </div>
  );
};

export default StatCard;
